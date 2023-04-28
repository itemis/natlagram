"""this module contains the REPL class, which is used to interact with the chatbot in the terminal."""

from pathlib import Path
from typing import Tuple

import chatGPT_official as chatGPT
from chatGPT_official import InteractionMode
import kroki
import const

class REPL:
    """read-eval-print loop for interacting with the chatbot in the terminal"""

    def __init__(self) -> None:
        kroki.check_kroki_server()
        self.chatbot = chatGPT.Model()
        self.chatbot.load_primers()
        if const.DEBUG == False:
            self.chatbot.load_examples()
        self.chatbot.backup_messages()
        self.workdir = Path("temp")

        tokens = self.chatbot.estimate_tokens()
        print(f"Estimated tokens: {tokens}")

    def print_pretty_text(self, code: str, api: str, text: str, i: int) -> None:
        """print the model's response text and extracted code and API without redundancy
        
        args:
            code: the code extracted from the model's response
            api: the API extracted from the model's response
            text: the full response text from the model
            i: the index of the message, if multiple messages were generated from a single user prompt
        """
        if code and api and code in text:
            print(f"Code [{i}]:\n{code}")
            print(f"API [{i}]: {api}")
        else:
            print(f"Text [{i}]: {text}")

    def generate_image(self, text: str, i: int, retry: int = 0) -> bool:
        """generate an image from a model's response
        
        args:
            text: the text extracted from the model's response 
            i: the index of the message, if multiple messages were generated from a single user prompt
            retry: the number of times the image generation has been retried for a given user input

        returns:
            True if the image was generated successfully, False otherwise
        """
        print(f"Tokens: {self.chatbot.estimate_tokens()}")
        if retry > 0:
            print(f"Bot response [{i}], retry [{retry}]:")
        else:
            print(f"Bot response [{i}]:")
        try:
            code = self.chatbot.extract_code_from_response(text)
            api = self.chatbot.extract_diagram_api_from_response(text)
        except:
            code = ""
            api = ""
        self.print_pretty_text(code, api, text, i)

        img_url = kroki.generate_url_from_str(code, api, "svg")
        print(f"URL [{i}]: {img_url}")

        valid = kroki.check_image_valid(img_url, api, code)
        print(f"Valid [{i}]: {valid}")

        if valid:
            kroki.save_images(img_url, self.workdir, api, code)
            return True

        return False

    def retry_with_hi_temp(self, prompt: str) -> str:
        """generate a message with a higher temperature
        
        args:
            prompt: the user prompt to generate a message from
        """
        hi_temp = self.chatbot.get_hi_temp()
        texts = self.chatbot.generate_message(prompt, temperature=hi_temp, n=1) # generate only one message
        return texts[0] # there is only one text in the list

    def handle_special_prompt_cases(self, prompt: str) -> Tuple[bool, str]:
        """handle a user prompt on the surface level
        
        args:
            prompt: the user prompt
                options:
                    1) "exit": quit REPL
                    2) "multiline": enter multiline queries
                    3) ["stateless", "improve", "stateful"]: change interaction mode
        
        returns: 
            a tuple with
                a boolean indicating whether the interaction mode was modified
                the user prompt, optionally modified
        """
        old_mode = self.chatbot.interaction_mode
        changed = False

        if prompt == "exit":
            exit()
        if prompt == "multiline":
            print("Enter your multiline prompt. Type 'end' to finish.")
            lines = []
            while True:
                line = input()
                if line == "end":
                    break
                lines.append(line)
            prompt = "\n".join(lines)
        elif prompt == "stateless":
            self.chatbot.set_interaction_mode(InteractionMode.STATELESS)
        elif prompt == "improve":
            self.chatbot.set_interaction_mode(InteractionMode.IMPROVING)
        elif prompt == "stateful":
            self.chatbot.set_interaction_mode(InteractionMode.STATEFUL)

        if old_mode != self.chatbot.interaction_mode:
            changed = True

        if changed:
            print(f"Interaction mode: {self.chatbot.interaction_mode}")
        
        return changed, prompt

    def handle_failure(self, prompt: str, success: bool, i: int, retry: int = 0) -> None:
        """handle a failure to generate an image from a model's response
        
        args:
            prompt: the user prompt
            text: the model's response text
            success: whether the image was generated successfully
            i: the index of the message, if multiple messages were generated from a single user prompt
            retry: the number of times handle_failure has been called recursively
        """

        def try_again() -> None:
            """user wants to try again"""
            texts = self.chatbot.generate_message(prompt, n=1) # generate only one message
            text = texts[0] # there is only one text in the list
            success = self.generate_image(text, i, retry + 1) # increment failure's index by 10 to avoid overlap with original messages
            self.handle_failure(prompt, success, i, retry + 1)

        if self.chatbot.interaction_mode == InteractionMode.STATELESS:
            if success:
                return
            else:
                print("Could not generate image.")

            user_response = input("Try again with same input? [y/n]: ")

            if user_response in ["y", "Y", "yes", "Yes", "YES"]:
                try_again()
    
        if self.chatbot.interaction_mode == InteractionMode.IMPROVING:
            if success:
                self.chatbot.restore_backup_messages()
                return
            else:
                print("Could not generate image.")
            
            user_response = input("Should I try to fix the code? [y/n]: ")

            if user_response in ["y", "Y", "yes", "Yes", "YES"]:
                try_again()
            else:
                self.chatbot.restore_backup_messages()
                print("Forgetting our conversation.")

        if self.chatbot.interaction_mode == InteractionMode.STATEFUL:
            if success:
                return
            else:
                print("Could not generate image. Let me know what went wrong.")

    def start_repl(self):
        """start a REPL to interact with the model"""

        print("Welcome to the natlagram REPL!") # natlagram = natural language diagram
        print("Type 'exit' to exit the REPL.")
        print(f"Type 'stateless', 'improve' or 'stateful' to change interaction mode. Default {self.chatbot.interaction_mode}.")
        print(f"Type 'multiline' to enter multiline queries.")
        
        while True:
            prompt = input("User: ")
            mode_changed, prompt = self.handle_special_prompt_cases(prompt)
            if mode_changed:
                continue
            
            texts = self.chatbot.generate_message(prompt) # generated n responses by the model
            for i, text in enumerate(texts):
                success = self.generate_image(text, i)
                self.handle_failure(prompt, success, i)

if __name__ == "__main__":
    repl = REPL()
    repl.start_repl()