# Currently a WIP. (Heroku took it down. Might rebuild this and deploy to Render)

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
    - `POSTGRES_NAME`
    - `POSTGRES_PASSWORD`
    - `POSTGRES_PORT`
    - `POSTGRES_DB`
    - `POSTGRES_HOST` 
    - `REMIXIFY`
    - `SITE_ID`
    - `ALLOWED_HOSTS`
    - `REDIS_URL`
    - `CELERY_RESULT_BACKEND`
    - `CELERY_CACHE_BACKEND`


Example can be found in `.env_local.txt` in the root directory:

## Running

1. Run `docker-compose up` in root directory to spin up necessary services and dependencies.


## Common Error When Logging In

1.  `Social Matching App Query Does Not Exist`

This results from improper choice of `SITE_ID` environment variable. To find the correct site ID:
  
- `Site.objects.values_list('id', flat=True)` to list the IDs.
