import stripe
from flask import url_for
import os

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

def create_checkout_session(price_id, user_email):
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=url_for('payment_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('payment_canceled', _external=True),
            customer_email=user_email
        )
        return session.url
    except Exception as e:
        print(f"Erro no Stripe: {str(e)}")
        return None