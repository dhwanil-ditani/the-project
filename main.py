import typer


app = typer.Typer()


@app.command()
def run_server():
    import uvicorn
    import backend
    uvicorn.run(backend.app, port=8000)


if __name__ == "__main__":
    app()
