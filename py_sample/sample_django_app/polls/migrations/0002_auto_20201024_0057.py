# Generated by Django 3.1.2 on 2020-10-23 15:57

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('polls', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='question',
            old_name='quenstion_text',
            new_name='question_text',
        ),
    ]
