"""alpha-engagement :8455 — behavioral finance (FBS) and reward economy."""

from services.runtime.bootstrap import create_service_app, run_service

ROUTERS = [
    "behavioral",
    "rewards",
]


def setup_engagement_scheduler(app, logger):
    """Start Monday 00:00 Asia/Jakarta weekly reward rotation scheduler."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from packages.core.domain.services.reward_rotation_service import RewardRotationService

        scheduler = BackgroundScheduler()
        trigger = CronTrigger(day_of_week="mon", hour=0, minute=0, timezone="Asia/Jakarta")

        def run_weekly_rotation_job():
            try:
                service = RewardRotationService()
                pool = service.rotate_week()
                logger.info(f"Weekly reward rotation completed: week_start={pool.get('week_start')}")
            except Exception as e:
                logger.error(f"Weekly reward rotation failed: {e}", exc_info=True)

        scheduler.add_job(
            run_weekly_rotation_job,
            trigger=trigger,
            id="weekly_reward_rotation",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("Engagement weekly reward rotation scheduler started (Mon 00:00 Asia/Jakarta).")
    except Exception as e:
        logger.warning(f"Engagement scheduler setup skipped/failed: {e}")


app = create_service_app(
    service_name="alpha-engagement",
    default_port=8455,
    routers=ROUTERS,
    register_inline=setup_engagement_scheduler,
)

if __name__ == "__main__":
    run_service(app, "alpha-engagement")
