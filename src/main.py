import asyncio
import logging
import socket
from contextlib import suppress
from pathlib import Path

# Disable verbose httpx/httpcore logging BEFORE any imports
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

import uvicorn

from .api import create_app
from .config import settings, validate_settings
from .relay import RelayCoordinator

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure logging with both console and file output."""
    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)
    
    # File handler (rotating, max 10MB per file, keep 5 backups)
    try:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            logs_dir / "bot.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.INFO)
        file_format = logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_format)
        root_logger.addHandler(file_handler)
        logger.info(f"Logging to file: {logs_dir / 'bot.log'}")
    except Exception as e:
        logger.warning(f"Failed to set up file logging: {e}")
    
    # Ensure httpx/httpcore logging stays at WARNING level
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    # Suppress pydle verbose logging
    logging.getLogger("pydle").setLevel(logging.WARNING)


def _is_port_in_use(host: str, port: int) -> bool:
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


async def run_api(coordinator: RelayCoordinator) -> None:
    """Run the FastAPI server using uvicorn."""
    # Check if port is available before starting
    if _is_port_in_use(settings.api_host, settings.api_port):
        logger.error(
            f"Port {settings.api_port} is already in use. "
            f"Please stop the process using this port or change API_PORT in your .env file."
        )
        logger.error(
            f"To find what's using the port, run: lsof -i :{settings.api_port} "
            f"or (on Linux) netstat -tulpn | grep :{settings.api_port}"
        )
        # Don't exit the entire process - just skip the API server
        # The bot can still run without the API server
        return
    
    app = create_app(coordinator, settings)
    config = uvicorn.Config(
        app=app,
        host=settings.api_host,
        port=settings.api_port,
        log_level="info",
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    
    try:
        await server.serve()
    except SystemExit as e:
        # Uvicorn may call sys.exit() on startup failure
        # Don't re-raise - just log and let the task complete
        if e.code != 0:
            logger.error(
                f"API server failed to start (exit code {e.code}). "
                f"This is often caused by port {settings.api_port} already being in use."
            )
        # Don't re-raise SystemExit - let the task complete normally
        # The bot can continue running without the API server
        return
    except OSError as e:
        logger.error(f"API server failed to bind to {settings.api_host}:{settings.api_port}: {e}")
        # Don't re-raise - just log and return
        return


async def main_async() -> None:
    configure_logging()
    
    # Set asyncio exception handler to suppress known harmless errors
    def _suppress_task_exceptions(loop, context):
        """Suppress annoying asyncio task exception warnings for known issues."""
        exception = context.get('exception')
        if exception:
            error_str = str(exception)
            # Suppress readuntil() errors - these are handled gracefully by our code
            if "readuntil() called while another coroutine is already waiting" in error_str:
                return  # Suppress this warning completely
            # Suppress other known harmless RuntimeErrors
            if isinstance(exception, RuntimeError) and "readuntil" in error_str.lower():
                return
        # For other exceptions, use default handler
        if hasattr(loop, 'default_exception_handler'):
            loop.default_exception_handler(context)
        else:
            # Fallback: just log at debug level
            logger.debug(f"Unhandled exception in task: {context}")
    
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(_suppress_task_exceptions)
    
    # Validate settings before starting
    try:
        validate_settings(settings)
        logger.info("Configuration validation passed")
    except RuntimeError as e:
        logger.error("Configuration validation failed. Please fix the errors and try again.")
        raise
    
    coordinator = RelayCoordinator(settings)

    api_task = asyncio.create_task(run_api(coordinator), name="uvicorn-server")
    irc_task = asyncio.create_task(coordinator.start_irc(), name="irc-client")

    try:
        await coordinator.start_discord()
    except asyncio.CancelledError:
        raise
    except Exception:
        logging.exception("Fatal error in Discord bot")
        raise
    finally:
        # Shutdown coordinator first (this will close Discord and IRC clients)
        try:
            await coordinator.shutdown()
        except Exception as e:
            logger.warning("Error during coordinator shutdown: %s", e)
        
        # Cancel tasks if they're still running
        if not api_task.done():
            api_task.cancel()
        if not irc_task.done():
            irc_task.cancel()
        
        # Wait for tasks to complete, suppressing cancellation and other errors
        # Use gather with return_exceptions to ensure all tasks are awaited
        tasks_to_wait = []
        if not api_task.done():
            tasks_to_wait.append(api_task)
        if not irc_task.done():
            tasks_to_wait.append(irc_task)
        
        if tasks_to_wait:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks_to_wait, return_exceptions=True),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.warning("Shutdown timeout, some tasks may not have completed cleanly")
            except Exception as e:
                logger.debug("Error waiting for tasks: %s", e)
        
        # Cancel any remaining pending tasks (except the current one)
        try:
            loop = asyncio.get_running_loop()
            pending_tasks = [t for t in asyncio.all_tasks(loop) if not t.done() and t is not asyncio.current_task()]
            if pending_tasks:
                logger.debug("Cancelling %d pending tasks", len(pending_tasks))
                for task in pending_tasks:
                    task.cancel()
                # Wait briefly for cancellations to propagate
                if pending_tasks:
                    await asyncio.gather(*pending_tasks, return_exceptions=True)
        except Exception as e:
            logger.debug("Error cancelling pending tasks: %s", e)
        
        # Give a small delay to allow any remaining cleanup
        await asyncio.sleep(0.1)


def main() -> None:
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logging.info("Interrupted, shutting down cleanly.")


if __name__ == "__main__":
    main()


