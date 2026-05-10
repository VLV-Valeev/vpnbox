from aiogram import Router

from . import admin, start, trial, subscription, payment, profile, stars_payment, referral

router = Router()
router.include_router(stars_payment.router)  # первым — перехватывает pay:*:stars и pre_checkout_query
router.include_router(admin.router)          # админ — до общих хендлеров
router.include_router(start.router)
router.include_router(trial.router)
router.include_router(subscription.router)
router.include_router(payment.router)
router.include_router(profile.router)
router.include_router(referral.router)
