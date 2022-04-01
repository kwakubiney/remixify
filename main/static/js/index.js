function handleSubmit(){
    document.querySelector("form").addEventListener("submit", function(e){
        e.preventDefault();
        formData = new FormData(e.target);
        formProps = Object.fromEntries(formData);
        fetch('/results/', {
        method: 'POST',
        body: formData
        })
        .then(response => response.json())
        .then(data => {
            // console.log('Success:', data);
            progressUrl = `/celery-progress/${data.task_id}`;
            return progressUrl
        }).then(progressUrl => CeleryProgressBar.initProgressBar(progressUrl))})}

document.addEventListener("DOMContentLoaded", handleSubmit)


