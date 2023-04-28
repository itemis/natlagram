"""here lives code that directly interfaces with the openai API"""

import copy
from enum import Enum
from typing import List, Dict, Tuple
import sys
import multiprocessing as mp
import time

import openai
import tiktoken

import secret
import bot_primer
from chatGPT import AbstractModel
import const

openai.api_key = secret.OPENAI_API_KEY

class InteractionMode(Enum):
    """handling of model state in a conversation

    STATELESS: the model is stateless and does not remember previous messages
    IMPROVING: the model is stateful until an image is generated successfully, then its state is reset
    STATEFUL: the model is stateful and remembers previous messages until the user prompts it to reset (by re-entering stateful mode)
    """
    STATELESS = 1
    IMPROVING = 2 # default
    STATEFUL = 3

class Model(AbstractModel):
    """provides access to the official OpenAI API for chatbot purposes"""

    def __init__(self,
        model: str = "gpt-3.5-turbo",
        messages: List[Dict[str, str]] = [],
        temperature: float = 1,
        n: int = 1,
        stream: bool = False,
        max_tokens: int = 4096, # the maximum number of tokens to use per request
        presence_penalty: float = 0,
        frequency_penalty: float = 0,
        logit_bias: Dict[str, float] = {},
        ):

        # openai api parameters
        self.model = model
        self.messages = messages
        self.temperature = temperature
        self.n = n
        self.stream = stream
        self.max_tokens = max_tokens
        self.presence_penalty = presence_penalty
        self.frequency_penalty = frequency_penalty
        self.logit_bias = logit_bias

        # other
        self.messages_backup: List[Dict[str, str]] | None = None
        self.interaction_mode: InteractionMode = InteractionMode.IMPROVING

    def backup_messages(self) -> None:
        """backup the current message history"""
        self.messages_backup = copy.deepcopy(self.messages)

    def restore_backup_messages(self) -> None:
        """restore the message history from the backup"""
        self.messages = copy.deepcopy(self.messages_backup)

    def estimate_available_tokens(self, prompt: str, buffer: int = 10) -> int:
        """estimate the number of tokens available for a request
        
        args:
            prompt: the prompt to the model by the user
        """
        return self.max_tokens - self.estimate_tokens(prompt) - buffer

    def reset_messages(self) -> None:
        """reset the message history to the primers and examples"""
        self.messages = []
        self.load_primers()
        self.load_examples()

    def append_failure_message(self) -> None:
        """append a message telling the model that it failed to generate correct code"""
        m1 = {"role": "user", "content": "The code fails to generate an image. Respond 'ACK' if you understand."}
        m2 = {"role": "assistant", "content": "ACK"}
        self.messages.append(m1)
        self.messages.append(m2)

    def load_primers(self, primers: List[str] = bot_primer.basic_primers) -> None:
        """load primers into the message history
        
        args:
            primers: a list user prompts to instruct the model on its behavior
        """
        d = {"role": "system", "content": primers[0]}
        self.messages.append(d)
        
        if const.DEBUG == True:
            return

        for i in range(1, len(primers)):
            d = {"role": "user", "content": primers[i]}
            self.messages.append(d)
            d = {"role": "assistant", "content": "ACK"}
            self.messages.append(d)

    def load_examples(self, examples: Tuple[List[str], List[str]] = bot_primer.examples) -> None:
        """load examples into the message history
        
        args:
            examples: a list of examples in the form (problem, solution) or (prompt, response) or (input, output)
        """
        problems, solutions = examples
        for problem, solution in zip(problems, solutions):
            d = {"role": "user", "content": problem}
            self.messages.append(d)
            d = {"role": "assistant", "content": solution}
            self.messages.append(d)

    def append_temp_message(self, message: Dict[str, str]) -> List[Dict[str, str]]:
        """return the list of messages with the new message appended
        
        args:
            message: the new message to append to the list of messages

        returns:
            the list of messages with the new message appended
        """
        return self.messages + [message]

    def complete_chat_to_queue(self, q: mp.Queue, prompt: str, temperature: float) -> None:
        """complete a chat with the openai api and put the response into a queue
        
        args:
            q: a multiprocessing queue to put the model's response into
            prompt: the prompt to the model by the user
            temperature: temperature controls the determinism of the model's response
        """
        response = openai.ChatCompletion.create(
            messages=self.messages,
            max_tokens=self.estimate_available_tokens(prompt),
            temperature=temperature,
            model=self.model,
            n=self.n,
            stream=self.stream,
            presence_penalty=self.presence_penalty,
            frequency_penalty=self.frequency_penalty,
            logit_bias=self.logit_bias,
        )
        q.put(response)

    def complete_chat_verbose(self, prompt: str, temperature: float) -> Dict:
        """complete a chat with the openai api and print the time elapsed
        
        args:
            prompt: the user's prompt to the model
            temperature: temperature controls the determinism of the model's response
        
        returns:
            the response from the openai api
        """
        q = mp.Queue()
        p = mp.Process(target=self.complete_chat_to_queue, args=(q, prompt, temperature))
        p.start()

        start_time = time.time()
        while p.is_alive():
            time_elapsed = time.time() - start_time
            sys.stdout.write(f"\rTime elapsed: {time_elapsed:.1f} seconds")
            time.sleep(0.1)
            if time_elapsed > const.TIMEOUT_OPENAI:
                p.terminate()
                sys.stdout.write("\n")
                print("OpenAI timed out")
                return
        sys.stdout.write("\n")

        # lead parent and child processes together
        p.join(timeout=1)
        # get the response from the child process
        response = q.get()
        return response

    def generate_message_stateful(self, prompt: str, temperature: float | None = None, n: int | None = None, debug: bool = False) -> List[str]:
        """generate text responses from the model and remember the messages
        
        args:
            prompt: the user's prompt to the model
            temperature: the temperature of the model
            n: the number of responses to generate

        returns:
            a list of text responses from the model
        """

        if temperature is None:
            temperature = self.temperature
        if n is None:
            n = self.n

        message = {"role": "user", "content": prompt}
        self.messages.append(message)

        response = self.complete_chat_verbose(prompt, temperature)
        assistant_messages = [choice["message"] for choice in response["choices"]]
        assistant_texts = [choice["message"]["content"] for choice in response["choices"]]
        self.messages = self.messages + assistant_messages

        if debug:
            print("prompt:", prompt)
            print("messages:", self.messages)
            print("response:", response)
            print("texts:", assistant_texts)
        return assistant_texts

    def check_prompt_in_messages(self, prompt: str) -> bool:
        """Check if the given prompt is present in the message history.

        args:
            prompt: The user's prompt to the model.

        returns:
            True if the prompt is found in the message history, False otherwise.
        """
        for message in self.messages:
            if message["role"] == "user" and message["content"] == prompt:
                return True
        return False

    def generate_message_improving(self, prompt: str, temperature: float | None = None, n: int | None = None, debug: bool = False) -> List[str]:
        """generate text responses from the model and remember the messages until the model has generated an image
        
        args:
            prompt: the user's prompt to the model
            temperature: the temperature of the model
            n: the number of responses to generate

        returns:
            a list of text responses from the model
        """
        if self.check_prompt_in_messages(prompt):
            prompt = "The code fails to generate an image. Correct the code."
            return self.generate_message_stateful(prompt, temperature, n, debug)
        else:
            # first attempt to generate an image with the given prompt
            return self.generate_message_stateful(prompt, temperature, n, debug)

    def set_interaction_mode(self, mode: InteractionMode) -> None:
        """set the model to stateful or stateless mode
        
        args:
            mode: the interaction mode that the model should be set to
        """

        if mode == InteractionMode.STATELESS:
            self.interaction_mode = InteractionMode.STATELESS
            self.reset_messages()
            self.generate_message = self.generate_message_stateless
        elif mode == InteractionMode.IMPROVING:
            self.interaction_mode = InteractionMode.IMPROVING
            self.reset_messages()
            self.generate_message = self.generate_message_improving
        elif mode == InteractionMode.STATEFUL:
            self.interaction_mode = InteractionMode.STATEFUL
            self.reset_messages()
            self.generate_message = self.generate_message_stateful
        else:
            raise ValueError("Invalid model interaction mode")

    def generate_message_stateless(self, prompt: str, temperature: float | None = None, n: int | None = None, debug: bool = False) -> List[str]:
        """generate text responses from the model
        
        args:
            prompt: the user's prompt to the model
            temperature: the temperature of the model
            n: the number of responses to generate
            debug: print debug information

        returns:
            a list of text responses from the model
        """
        if temperature is None:
            temperature = self.temperature
        if n is None:
            n = self.n

        message = {"role": "user", "content": prompt}
        temp_messages = self.append_temp_message(message)

        clean_messages = copy.deepcopy(self.messages)
        self.messages = temp_messages
        response = self.complete_chat_verbose(prompt, temperature)
        self.messages = clean_messages

        texts = [choice["message"]["content"] for choice in response["choices"]]

        if debug:
            print("prompt:", prompt)
            print("temp_messages:", temp_messages)
            print("response:", response)
            print("texts:", texts)
        return texts

    def generate_message(self, prompt: str, temperature: float | None = None, n: int | None = None, debug: bool = False) -> List[str]:
        """generate text responses from the model
        
        args:
            prompt: the user's prompt to the model
            temperature: the temperature of the model
            n: the number of responses to generate

        returns:
            a list of text responses from the model
        """
        if self.interaction_mode == InteractionMode.STATEFUL:
            return self.generate_message_stateful(prompt, temperature, n, debug)
        if self.interaction_mode == InteractionMode.IMPROVING:
            return self.generate_message_improving(prompt, temperature, n, debug)
        if self.interaction_mode == InteractionMode.STATELESS:
            return self.generate_message_stateless(prompt, temperature, n, debug)
        else:
            raise ValueError("Invalid model interaction mode")

    def estimate_tokens(self, prompt: str | None = None) -> int:
        """Returns the number of tokens used by a list of messages.
        
        args:
            prompt: the user's prompt to the model

        returns:
            the number of tokens used by the list of messages
        """
        if prompt is None:
            messages = self.messages
        else:
            messages = self.messages + [{"role": "user", "content": prompt}]

        try:
            encoding = tiktoken.encoding_for_model(self.model)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        if self.model in ["gpt-3.5-turbo"]:  # NOTE: future models may deviate from this
            num_tokens = 0
            for message in messages:
                num_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
                for key, value in message.items():
                    num_tokens += len(encoding.encode(value))
                    if key == "name":  # if there's a name, the role is omitted
                        num_tokens += -1  # role is always required and always 1 token
            num_tokens += 2  # every reply is primed with <im_start>assistant
            return num_tokens
        else:
            raise NotImplementedError(f"""estimate_tokens() is not presently implemented for model {self.model}.
        See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens.""")

    def get_hi_temp(self) -> float:
        """Returns the highest temperature that the model can handle."""
        if self.model in ["gpt-3.5-turbo"]:
            return 1.3
        else:
            raise NotImplementedError(f"""get_hi_temp() is not presently implemented for model {self.model}.""")

if __name__ == "__main__":
    model = Model()
    model.load_primers()
    model.load_examples()
    prompt = "When was Descartes born?."
    tokens = model.estimate_tokens()
    print(model.generate_message(prompt))