from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.filters.command import CommandObject
from aiogram.types import Message, CallbackQuery, LinkPreviewOptions, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repo import UserRepo, SubRepo
from app.bot import texts, keyboards
from app.services.subscription_service import activate_trial

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, command: CommandObject) -> None:
    tmp = await message.answer("⏳ Загрузка...", reply_markup=ReplyKeyboardRemove())

    try:
        user_repo = UserRepo(session)

        referrer_id = None
        args = command.args
        if args and args.startswith("ref_"):
            try:
                referrer_tg_id = int(args[4:])
                if referrer_tg_id != message.from_user.id:
                    referrer = await user_repo.get_by_tg(referrer_tg_id)
                    if referrer:
                        referrer_id = referrer.id
            except ValueError:
                pass

        user, is_new = await user_repo.get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
            referrer_id=referrer_id,
        )

        trial_available = not user.trial_used
        sub = await SubRepo(session).get_active(user.id)
        if sub:
            trial_available = False

        if is_new:
            text = texts.WELCOME + "\n\n" + texts.LEGAL_AGREEMENT
        elif not user.trial_used:
            text = texts.WELCOME
        else:
            text = texts.WELCOME_BACK

        if is_new and referrer_id:
            trial_result = await activate_trial(session, message.from_user.id)
            if trial_result.get("ok"):
                trial_available = False
                await message.answer(
                    text,
                    reply_markup=keyboards.main_menu(trial_available=False),
                    parse_mode="HTML",
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
                await message.answer(
                    texts.REFERRAL_TRIAL_BONUS.format(
                        expires=texts.fmt_date(trial_result["expires_at"]),
                        url=trial_result["subscription_url"],
                    ),
                    parse_mode="HTML",
                )
            else:
                await message.answer(
                    text,
                    reply_markup=keyboards.main_menu(trial_available),
                    parse_mode="HTML",
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
        else:
            await message.answer(
                text,
                reply_markup=keyboards.main_menu(trial_available),
                parse_mode="HTML",
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )

    except Exception:
        import logging
        logging.getLogger(__name__).exception("cmd_start error")
        await message.answer(
            "Произошла ошибка. Попробуйте ещё раз через несколько секунд.",
        )

    finally:
        # Удаляем "Загрузка..." в любом случае — и при успехе, и при ошибке
        try:
            await tmp.delete()
        except Exception:
            pass


@router.message(Command("info"))
async def cmd_info(message: Message) -> None:
    await message.answer(
        texts.INFO_TEXT,
        parse_mode="HTML",
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


@router.callback_query(F.data == "back:main")
async def back_to_main(callback: CallbackQuery, session: AsyncSession) -> None:
    user_repo = UserRepo(session)
    user = await user_repo.get_by_tg(callback.from_user.id)
    trial_available = user and not user.trial_used
    if user:
        sub = await SubRepo(session).get_active(user.id)
        if sub:
            trial_available = False

    await callback.message.edit_text(
        texts.WELCOME_BACK,
        reply_markup=keyboards.main_menu(trial_available),
        parse_mode="HTML",
    )
    await callback.answer()
