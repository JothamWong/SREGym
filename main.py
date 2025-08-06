import asyncio
import threading

from rich.console import Console

from api import run_api
from srearena.conductor.conductor import Conductor


def driver_loop(conductor: Conductor):
    """Run inside a thread: no SigintAwareSection here."""

    async def driver():
        console = Console()
        await asyncio.sleep(1)  # allow API to bind

        for pid in conductor.problems.get_problem_ids():
            console.log(f"\n🔍 Starting problem: {pid}")
            conductor.problem_id = pid
            await conductor.start_problem()

            with console.status(f"⏳ Waiting for grading… (stage={conductor.submission_stage})") as status:
                while conductor.submission_stage != "done":
                    await asyncio.sleep(1)
                    status.update(f"⏳ Waiting for grading… (stage={conductor.submission_stage})")

            console.log(f"✅ Completed {pid}: results={conductor.results}")

    asyncio.run(driver())


def main():
    conductor = Conductor()

    # 1) Start driver loop in background thread (no signals here)
    threading.Thread(target=lambda: driver_loop(conductor), daemon=True).start()

    # 2) Start HTTP API in main thread (signals allowed)
    print("📡 HTTP API server launching at http://0.0.0.0:8000")
    run_api(conductor, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
