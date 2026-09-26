FROM python:3.10-slim

# Create non-root user for Hugging Face Spaces (UID 1000)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR $HOME/app

# Install Python requirements
COPY --chown=user:user requirements.txt $HOME/app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY --chown=user:user . $HOME/app

# Create necessary runtime directories
RUN mkdir -p $HOME/app/data

# Expose official Hugging Face Spaces port
EXPOSE 7860

# Launch FastAPI app with Uvicorn on port 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
