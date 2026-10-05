"""AWS Lambda entry point for the FastAPI application."""

from mangum import Mangum

from rag_assistant.api import app


handler = Mangum(app)
