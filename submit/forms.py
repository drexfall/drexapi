from django import forms
from .models import UMalangContact


class UMalangContactForm(forms.ModelForm):
	class Meta:
		model = UMalangContact
		fields = ['name', 'email', 'subject', 'message']
