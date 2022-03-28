# creates a new Spotify playlist of remixes of songs in your favourite Spotify playlist <3

## Setting up

The server can be run locally but you will need to register your own Spotify app and set the credentials. The procedure is as follows:

1. Create an application on [Spotify's Developer Site](https://developer.spotify.com/my-applications/).

2. Add the redirect uri http://127.0.0.1:8000/accounts/spotify/login/callback/ on Spotify site(for development)


3. Create a `.env` file in the root of the project with the following variables;

    - `SECRET_KEY`
    - `CLIENT_ID`
    - `CLIENT_SECRET`
    - `REDIRECT_URI`
    - `DB_NAME`
    - `DB_PASSWORD`
    - `DB_PORT`
    - `DB_USER`
    - `DB_HOST` 

Example can be found in `.env_local` in the root directory:

## Dependencies

1. Install the dependencies running `pip install -r requirements.txt` after creating a virtual environment.

2. Run `py manage.py makemigrations` and `py manage.py migrate` in the base directory to setup the DB schemas.

## Running
1. To use celery workers etc, make sure you have `redis` installed on your machine. It is going to be used as a message broker to queue tasks for `celery` workers.

2. Run `python manage.py runworker` to start a `celery` worker in another terminal.

3. Run `python manage.py runserver` to start developer server.


