import gradio as gr
from main import app as fastapi_app
import spaces

@spaces.GPU
def dummy_gpu(text):
    return text

demo = gr.Interface(fn=dummy_gpu, inputs="text", outputs="text")

# Mount Gradio onto our FastAPI app. Hugging Face runs `app` if it finds it.
app = gr.mount_gradio_app(fastapi_app, demo, path="/gradio")
