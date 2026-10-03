from django.db import models


class Comuna(models.Model):
    """De la hoja 'Comunas': tabla región → comuna."""

    nombre = models.CharField(max_length=100, unique=True)
    region = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Comuna"
        verbose_name_plural = "Comunas"
        ordering = ["region", "nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.region})"


class Promocion(models.Model):
    """De la hoja 'Apoyo': catálogo de promociones y qué RGU/servicios trae cada una."""

    class Empresa(models.TextChoices):
        VTR = "VTR", "VTR"
        CLARO = "CLARO", "Claro"

    nombre = models.CharField(max_length=150, unique=True)
    rgu = models.PositiveSmallIntegerField(default=1)
    tiene_internet = models.BooleanField(default=False)
    tiene_tv = models.BooleanField(default=False)
    tiene_fono = models.BooleanField(default=False)
    empresa = models.CharField(max_length=10, choices=Empresa.choices)
    canal = models.CharField(max_length=50, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Promoción"
        verbose_name_plural = "Promociones"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
