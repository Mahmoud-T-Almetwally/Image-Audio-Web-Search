import asyncio
import logging
import sys
import os
import shutil

logger = logging.getLogger(__name__)

PYTHON_EXECUTABLE = sys.executable
SCRAPY_EXECUTABLE = shutil.which("scrapy") or "scrapy"


SERVER_DIR = os.path.dirname(os.path.abspath(__file__))

SRC_DIR = os.path.dirname(SERVER_DIR)

SCRAPY_PROJECT_DIR_CONFIG = os.path.join(SRC_DIR, "web_scraper")


SETTINGS_MODULE_PATH = "web_scraper.web_scraper.settings"


async def launch_scrapy_crawl_async(
    job_id: str,
    start_url: str,
    allowed_domains: str,
    depth_limit: int,
    use_playwright: bool,
    crawl_strategy: str,
) -> asyncio.subprocess.Process:
    """
    Launches a Scrapy crawl process as a non-blocking subprocess,
    setting PYTHONPATH and SCRAPY_SETTINGS_MODULE.
    """

    if not os.path.isfile(os.path.join(SCRAPY_PROJECT_DIR_CONFIG, "scrapy.cfg")):
        logger.error(
            f"Scrapy config file (scrapy.cfg) not found at: {SCRAPY_PROJECT_DIR_CONFIG}"
        )
        raise FileNotFoundError(
            f"Scrapy config file not found: {SCRAPY_PROJECT_DIR_CONFIG}"
        )

    command_args = [
        SCRAPY_EXECUTABLE,
        "crawl",
        "media",
        "-a",
        f"start_url={start_url}",
        "-a",
        f"allowed_domains={allowed_domains}",
        "-a",
        f"depth_limit={depth_limit}",
        "-a",
        f"use_playwright={use_playwright}",
        "-a",
        f"crawl_strategy={crawl_strategy}",
        "-s",
        f"JOB_ID={job_id}",
    ]

    cwd = SCRAPY_PROJECT_DIR_CONFIG

    process_env = os.environ.copy()

    paths_to_add = [SRC_DIR]
    existing_pythonpath = process_env.get("PYTHONPATH")
    new_pythonpath = os.pathsep.join(paths_to_add)
    if existing_pythonpath:
        process_env["PYTHONPATH"] = f"{new_pythonpath}{os.pathsep}{existing_pythonpath}"
    else:
        process_env["PYTHONPATH"] = new_pythonpath

    process_env["SCRAPY_SETTINGS_MODULE"] = SETTINGS_MODULE_PATH

    logger.info(f"Job ID [{job_id}]: Launching Scrapy crawl...")
    logger.info(f"Job ID [{job_id}]: Command: {' '.join(command_args)}")
    logger.info(f"Job ID [{job_id}]: CWD: {cwd}")
    logger.info(
        f"Job ID [{job_id}]: Subprocess PYTHONPATH: {process_env.get('PYTHONPATH')}"
    )
    logger.info(
        f"Job ID [{job_id}]: Subprocess SCRAPY_SETTINGS_MODULE: {process_env.get('SCRAPY_SETTINGS_MODULE')}"
    )

    try:
        process = await asyncio.create_subprocess_exec(
            *command_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=process_env,
        )

        logger.info(
            f"Job ID [{job_id}]: Scrapy process started with PID: {process.pid}"
        )

        stdout_task = asyncio.create_task(read_stream(process.stdout, job_id, "stdout"))
        stderr_task = asyncio.create_task(read_stream(process.stderr, job_id, "stderr"))

        return process

    except FileNotFoundError:
        logger.error(
            f"Job ID [{job_id}]: Scrapy executable '{SCRAPY_EXECUTABLE}' not found."
        )
        raise
    except Exception as e:
        logger.error(
            f"Job ID [{job_id}]: Failed to launch Scrapy process: {e}", exc_info=True
        )
        raise


async def read_stream(stream, job_id, stream_name):
    while True:
        line = await stream.readline()
        if line:
            try:
                line_str = line.decode("utf-8").rstrip()
                logger.info(f"Job ID [{job_id}] ({stream_name}): {line_str}")
            except UnicodeDecodeError:
                logger.warning(
                    f"Job ID [{job_id}] ({stream_name}): Could not decode line (non-utf8): {line!r}"
                )
        else:
            break


async def main_test():
    print("--- Testing Scrapy Trigger ---")
    test_job_id = "test-job-123"
    test_url = "https://quotes.toscrape.com/"
    process = None
    stdout_task = None
    stderr_task = None
    try:
        process = await launch_scrapy_crawl_async(
            job_id=test_job_id,
            start_url=test_url,
            allowed_domains="quotes.toscrape.com",
            depth_limit=1,
            use_playwright=False,
            crawl_strategy="default",
        )
        timeout_seconds = 20
        try:
            logger.info(
                f"Waiting up to {timeout_seconds}s for subprocess {process.pid} to complete..."
            )

            await asyncio.wait_for(process.wait(), timeout=timeout_seconds)
            logger.info(
                f"Subprocess {process.pid} finished with return code: {process.returncode}"
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"Subprocess {process.pid} did not complete within {timeout_seconds}s. Terminating."
            )
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                logger.warning(
                    f"Subprocess {process.pid} did not terminate gracefully. Killing."
                )
                process.kill()
            except ProcessLookupError:
                logger.info(f"Subprocess {process.pid} already exited.")
            except Exception as term_err:
                logger.error(f"Error during process termination: {term_err}")
                if stdout_task:
                    try:
                        await asyncio.wait_for(stdout_task, timeout=2)
                    except asyncio.TimeoutError:
                        logger.warning("stdout reader task timed out.")
                if stderr_task:
                    try:
                        await asyncio.wait_for(stderr_task, timeout=2)
                    except asyncio.TimeoutError:
                        logger.warning("stderr reader task timed out.")

        print("Test finished.")
    except Exception as e:
        print(f"Error during trigger test: {e}")
    finally:

        if process and process.returncode is None:
            logger.warning(
                f"Process {process.pid} still running in finally block, attempting kill."
            )
            try:
                process.kill()
            except ProcessLookupError:
                pass
            except Exception as kill_err:
                logger.error(f"Error killing process in finally block: {kill_err}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s",
    )

    try:
        asyncio.run(main_test())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested via KeyboardInterrupt.")
