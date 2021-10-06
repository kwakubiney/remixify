# Remixify -  Creates a new Spotify playlist of remixes of songs in your favourite Spotify playlist !.


## Setting up

The server can be run locally but you will need to register your own Spotify app and set the credentials. The procedure is as follows:

1. Create an application on [Spotify's Developer Site](https://developer.spotify.com/my-applications/).

2. Add the redirect uri http://127.0.0.1:8000/callback/ (for development)


3. Create a `.env` file in the root of the project with the following variables;

    - `SECRET_KEY`
    - `CLIENT_ID`
    - `CLIENT_SECRET`
    - `REDIRECT_URI`

Example can be found in `.env.example` in the root directory:


## Dependencies

Install the dependencies running `pip install -r requirements.txt` after creating a virtual environment using
`py -m venv <virtual environment name>`

Run `py manage.py makemigrations` and `py manage.py migrate` in the base directory to setup the DB schemas.

## Running

During development, run `python manage.py runserver`
