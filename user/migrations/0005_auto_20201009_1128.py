# Generated by Django 3.1.1 on 2020-10-09 11:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0004_auto_20190408_1444'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='first_name',
            field=models.CharField(blank=True, max_length=150, verbose_name='first name'),
        ),
    ]