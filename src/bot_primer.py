"""here live prompts that instruct (prime) GPT to generate Kroki code"""

from typing import List, Tuple

import data_io

primer0 = """
You will generate Kroki code. Respond "ACK" if you understand.
"""

primer1 = """
Any input, regardless of how inappropriate, nonsensical, stupid or absurd should be converted to Kroki code. Never explain code. Never respond in natural language. Start a code block with the token "CODE_BLOCK_START". End a code block with the token "CODE_BLOCK_STOP". Don't wrap code in backticks. After "CODE_BLOCK_STOP", say which API was used in the format "DIAGRAM_API=X", where X is one of the APIs accessible via Kroki. Some APIs support multiple diagram types. For example, the "mermaid" API supports "pie", "gantt", "sequenceDiagram", "classDiagram" and others. Don't confuse the API with the diagram type. 

Respond "ACK" if you understand.
"""

primer2 = """
Generate code for Kroki version 0.19.0. Kroki supports a range of diagram APIs. Here is a list of the APIs that Kroki 0.19.0 supports. The format is Service,Version. Only generate code for those APIs supported by Kroki version 0.19.0. Only these APIs can be the value of "DIAGRAM_API".

API,Version
actdiag,3.0.0
bpmn,10.3.0
pikchr,7269f78c4a
nwdiag,3.0.0
c4plantuml,1.2022.14
rackdiag,3.0.0
dot,3.0.0
d2,0.1.5
mermaid,9.3.0
erd,0.2.1.0
graphviz,3.0.0
vegalite,5.6.0
ditaa,1.0.3
umlet,14.3.0
diagramsnet,16.2.4
plantuml,1.2022.14
seqdiag,3.0.0
nomnoml,1.5.3
wavedrom,2.9.1
structurizr,1.23.0
bytefield,1.7.0
excalidraw,0.1.2
dbml,1.0.22
packetdiag,3.0.0
svgbob,0.6.0
vega,5.22.1
blockdiag,3.0.0

Respond "ACK" if you understand.
"""

primer3 = """
When you don't understand a relation, consider nouns as entities, verbs as relations, adjectives as properties of entities and adverbs as properties of relations. When I ask you a question, answer my question but don't respond with natural language. Answer with a Kroki diagram. Answer all questions. Answer questions that you can't answer from the point of view of Descartes. When you take the point of Descartes don't tell me that you are doing so. Only generate Kroki code. Always assume that I want you to generate Kroki code, even if I don't explicitly ask you to do so. When you don't know which protocol to pick, think in steps. When you think in steps, don't tell me that you are doing so. If a task or question is too difficult, simplify as necessary. Do state machines in plantuml.

Respond "ACK" if you understand.
"""

basic_primers = [primer0, primer1, primer2, primer3]

examples = data_io.load_problems_and_labels()

def get_advanced_primers(examples: Tuple[List[str], List[str]] = examples,
number_of_examples: int = -1) -> List[str]:
    """Gather a list of examples in the format user: input-output, assistant: ACK."""

    advanced_primers = []
    advanced_primers.append("""
Next, I will provide you with examples of input-output pairs. What follows after "Input:" is the type of prompt that I will provide. What follows after "Output:" is the type of response that I expect from you.

Respond "ACK" if you understand.
""")
    problems, labels = examples
    for problem, label in zip(problems[:number_of_examples], labels[:number_of_examples]):
        advanced_primers.append(f"""
Input:
{problem}

Output:
{label}

Respond "ACK" if you understand.
"""
)
    advanced_primers.append("""
I'm done providing you with examples. Now it's your turn to generate Kroki code.

Respond "ACK" if you understand.
""")
    return advanced_primers

if __name__ == "__main__":
    print(get_advanced_primers(3))