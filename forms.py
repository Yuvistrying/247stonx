from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError
import re

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=20)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

class AddTickerForm(FlaskForm):
    ticker = StringField('Ticker Symbol', validators=[DataRequired(), Length(min=1, max=10)])
    submit = SubmitField('Add')
    
    def validate_ticker(self, ticker):
        # Ticker symbols can only contain letters and sometimes numbers or dots
        if not re.match(r'^[A-Za-z0-9\.]+$', ticker.data):
            raise ValidationError('Invalid ticker symbol format') 