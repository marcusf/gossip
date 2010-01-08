# Create your views here.
import datetime, random, sha
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.core.mail import send_mail
from zoid.prefs.forms import RegistrationForm
from django import forms


def register(request):
    c = RequestContext(request,{})

    if request.user.is_authenticated():
        # They already have an account; don't let them register again
        return render_to_response('register.html', {'has_account': True})
    manipulator = RegistrationForm()
    if request.POST:
        new_data = request.POST.copy()
        errors = manipulator.get_validation_errors(new_data)
        if not errors:
            # Save the user                                                                                                                                                 
            manipulator.do_html2python(new_data)
            new_user = manipulator.save(new_data)            
            return render_to_response('register.html', {'created': True}, c)
    else:
        errors = new_data = {}
    form = forms.FormWrapper(manipulator, new_data, errors)
    return render_to_response('register.html', {'form': form}, c)