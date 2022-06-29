# How it looks

![gif-remixify](https://user-images.githubusercontent.com/71296367/161169298-092aef1e-c8c3-4629-ad5e-704036d42d5b.gif)


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
    - `REMIXIFY`
    - `SITE_ID`
    - `ALLOWED_HOSTS`
    - `REDIS_URL`
    - `CELERY_RESULT_BACKEND`
    - `CELERY_CACHE_BACKEND`


Example can be found in `.env_local.txt` in the root directory:

## Dependencies

1. Install the dependencies running `pip install -r requirements.txt` after creating a virtual environment.

2. Run `py manage.py makemigrations` and `py manage.py migrate` in the base directory to setup the DB schemas.

## Running
1. To use celery workers etc, make sure you have `redis` installed on your machine. It is going to be used as a message broker to queue tasks for `celery` workers.

2. To enable proper login flow with `django-allauth`, create a Social Application from the admin page and choose `Spotify` as the provider,
   fill in your client ID and secret, and choose a site for your development. Example: `http://127.0.0.1:8000`

3. Run `python manage.py runworker` to start a `celery` worker in another terminal.
   # note : Celery is not supported on Windows so running the command above on Windows OS might not work.
   
   You can try to run `celery -A main worker -l info` manually from `main` directory in terminal to start workers but I cannot vouch for that 100%.

4. Run `python manage.py runserver` to start developer server.

## Common Error

1.  `Social Matching App Query Does Not Exist`

This results from improper choice of `SITE_ID` environment variable as it to be the ID of the site you created above. To find the correct site:
 
- You can open Python shell and import the Site model and run a `Site.objects.all()` to help identify the ID of your site.
  
- `Site.objects.values_list('id', flat=True)` will give a much clearer response.