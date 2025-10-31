from transformers import pipeline
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

help(summarizer)                 # full docstring
# or:
import inspect
print(inspect.signature(summarizer.__call__))  # callable signature
