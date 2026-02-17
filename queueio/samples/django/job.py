from django.db import models
from django.http import JsonResponse

from queueio import routine


class Job(models.Model):
    status = models.CharField(max_length=20, default="pending")
    objects = models.Manager()  # pyright: ignore[reportAssignmentType]

    class Meta:
        app_label = "queueio_sample"


@routine(name="update_job", queue="django")
def update_job(job_id: int):
    job = Job.objects.get(pk=job_id)
    job.status = "complete"
    job.save()


def index(request):
    if request.method == "POST":
        job = Job.objects.create()
        update_job(job.pk).submit()
        return JsonResponse({"job_id": job.pk, "status": job.status})

    job = Job.objects.latest("pk")
    return JsonResponse({"job_id": job.pk, "status": job.status})
