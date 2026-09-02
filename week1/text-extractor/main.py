from fastapi import FastAPI
from controller.document_extraction_controller import router

app = FastAPI()
app.include_router(router)

def main():
    print("Hello from text-extractor!")


if __name__ == "__main__":
    main()
