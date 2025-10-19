# Chain of Thought
* Always think step by step how to solve the problem.
* Always think each step in English.
* Always transform the input prompt into thoughts in English.
* When generating code, always generate annotations for input and output typing in the functions.
* Always comment on the step-by-step of what the code is generating (except when requested not to).

# Custom Instructions
* Always generate the code in English with comments in English and variables and instructions in English.
* Always take into account the simplest and most efficient way to solve a code problem.
* Always take into account the context.
* Follow the instructions provided.
* Always generate complete code, without leaving implicit code that would be generated in other steps (except when requested).


# Good Programming Practices
* Whenever possible, generate code in Python 3.11 or higher.
* Whenever possible, use the standard Python libraries.
* Whenever possible, use popular and well-maintained libraries.
* Whenever possible, use good programming practices.
* Whenever possible, use static typing (type hints).
* Whenever possible, use error handling and approaches.
* Whenever possible, use docstrings to document classes, methods, and functions.
* Whenever possible, use logging to record events and errors.

# Run Scripts
* Whenever possible, create CLI scripts to execute core functionality.
* Whenever possible, run generated or modified scripts to ensure they work correctly.
* Always run Python code via uv run python <script>.py