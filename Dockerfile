FROM public.ecr.aws/lambda/python:3.12

WORKDIR ${LAMBDA_TASK_ROOT}

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir ".[deploy]"

CMD ["rag_assistant.lambda_handler.handler"]
