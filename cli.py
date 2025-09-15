"""
SREArena CLI client. Use this for debugging and platform development work—
otherwise use main.py.

This version talks directly to the in-process Conductor for both environment
setup and grading, but still gives you the PromptToolkit+Rich UI.
"""

import asyncio
import json
import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from srearena.conductor.conductor import Conductor
from srearena.service.shell import Shell
from srearena.generators.noise.transient_issues import FaultType, PodScope

WELCOME = """
# SREArena
- Type your commands or actions below.
"""

OPTIONS = """
- Use `start <problem_id>` to begin a new problem.
- Use `deploy <app_name>` / `undeploy <app_name>` to manage standalone apps.
- Use `list` to see deployed apps.
- Use `options` to re-print this list.
- Use `exit` to quit.
"""

WARNING = (
    "[bold yellow][WARNING][/bold yellow] Starting a new problem will "
    "restart any running app. Make sure you finish working before you start."
)

# (If you still want TASK_MESSAGE for problem context, you can re-enable it here.)


class HumanAgent:
    def __init__(self, conductor: Conductor):
        self.session = PromptSession()
        self.console = Console(force_terminal=True, color_system="auto")
        self.conductor = conductor
        self.pids = self.conductor.problems.get_problem_ids()
        self.completer = WordCompleter(
            ["list", "options", "exit"] + [f"start {pid}" for pid in self.pids],
            ignore_case=True,
            match_middle=True,
            sentence=True,
        )
        self.session_purpose = None  # "problem", "exit", etc.

    def display_welcome(self):
        self.console.print(Markdown(WELCOME), justify="center")
        self.console.print(Markdown(OPTIONS), justify="center")
        self.console.print(WARNING)
        self.console.print()

    async def select_mode(self):
        """Prompt until we get 'start <problem_id>' or 'exit'."""
        while True:
            inp = await self._prompt()
            cmd = inp.strip().split(maxsplit=1)
            if cmd[0].lower() == "exit":
                sys.exit(0)
            if cmd[0].lower() == "options":
                self.console.print(Markdown(OPTIONS), justify="center")
                continue
            if cmd[0].lower() == "list":
                apps = self.conductor.get_deployed_apps()
                text = "\n".join(apps) if apps else "No apps deployed"
                self.console.print(Panel(text, title="Deployed Apps"))
                continue
            # if cmd[0].lower() == 'noise':
            #     await self.configure_transient_issues()
            #     continue
            if cmd[0].lower() == "start" and len(cmd) == 2:
                pid = cmd[1]
                if pid not in self.pids:
                    self.console.print(f"[red]Unknown problem id: {pid}")
                    continue
                self.conductor.problem_id = pid
                self.session_purpose = "problem"
                return
            self.console.print("[red]Invalid command. Type `options` to see choices.")

    async def interactive_loop(self):
        """Once problem is started, repeatedly shell or submit until done."""
        env = ""
        while self.conductor.submission_stage != "done":
            # display last environment or grading response
            if env:
                print(env)

            inp = await self._prompt()
            text = inp.strip()

            # shell command
            if not text.startswith("submit("):
                try:
                    out = Shell.exec(text)
                except Exception as e:
                    out = f"[❌] Shell error: {e}"
                env = out
                continue

            wrapped = f"```\n{text}\n```"
            try:
                resp = await self.conductor.submit(wrapped)
            except Exception as e:
                env = f"[❌] Grading error: {e}"
            else:
                env = resp

        # final results panel
        final = json.dumps(self.conductor.results, indent=2)
        self.console.print(Panel(final, title="Final Results", style="bold green"))

    async def _prompt(self) -> str:
        loop = asyncio.get_running_loop()
        style = Style.from_dict({"prompt": "ansigreen bold"})
        prompt_txt = [("class:prompt", "SREArena> ")]
        with patch_stdout():
            try:
                return await loop.run_in_executor(
                    None,
                    lambda: self.session.prompt(prompt_txt, style=style, completer=self.completer),
                )
            except (KeyboardInterrupt, EOFError):
                sys.exit(0)

    async def configure_transient_issues(self):
        """Interactive configuration for transient issues"""
        self.console.print("\n[bold blue]🔧 Configure Transient Issues Parameters[/bold blue]")
        
        config = {}
        
        # Switch to enable/disable transient issues
        config['switch'] = True

        # Duration settings
        self.console.print("\n[yellow]Duration Settings:[/yellow]")
        min_dur = await self._prompt_with_default("Minimum duration (seconds)", "40")
        max_dur = await self._prompt_with_default("Maximum duration (seconds)", "60")
        config['min_duration'] = int(min_dur)
        config['max_duration'] = int(max_dur)
        
        # Fault types
        self.console.print("\n[yellow]Fault Types (comma-separated):[/yellow]")
        self.console.print("Available: fail-stop, fail-slow")
        fault_input = await self._prompt_with_default("Fault types", "fail-stop,fail-slow")
        fault_types = []
        for ft in fault_input.split(','):
            ft = ft.strip()
            if ft == "fail-stop":
                fault_types.append(FaultType.FAIL_STOP)
            elif ft == "fail-slow":
                fault_types.append(FaultType.FAIL_SLOW)
        config['fault_types'] = fault_types
        
        # Scopes
        self.console.print("\n[yellow]Scopes (comma-separated):[/yellow]")
        self.console.print("Available: target_service, target_namespace, non_target_service, all_pods, non_target_namespace")
        scope_input = await self._prompt_with_default("Scopes", "target_namespace")
        scopes = []
        scope_map = {
            "target_service": PodScope.TARGET_SERVICE,
            "target_namespace": PodScope.TARGET_NAMESPACE,
            "non_target_service": PodScope.NON_TARGET_SERVICE,
            "all_pods": PodScope.ALL_PODS,
            "non_target_namespace": PodScope.NON_TARGET_NAMESPACE
        }
        global_faulty_service_pids = ['rpc_retry_storm']
        for scope in scope_input.split(','):
            scope = scope.strip()
            if scope == "target_service" and self.conductor.problem_id in global_faulty_service_pids:
                raise ValueError("target_service scope is not allowed for problems with global faulty services.")
            if scope in scope_map:
                scopes.append(scope_map[scope])
        config['scopes'] = scopes
        
        # Injection intervals
        self.console.print("\n[yellow]Injection Intervals:[/yellow]")
        int_min = await self._prompt_with_default("Minimum interval (seconds)", "20")
        int_max = await self._prompt_with_default("Maximum interval (seconds)", "30")
        config['interval_min'] = int(int_min)
        config['interval_max'] = int(int_max)
        
        # Apply configuration
        self.conductor.configure_transient_issues(**config)
        
        return config

    async def _prompt_with_default(self, prompt_text: str, default: str) -> str:
        """Prompt with default value"""
        full_prompt = f"{prompt_text} [{default}]: "
        result = await self._prompt_custom(full_prompt)
        return result.strip() or default

    async def _prompt_custom(self, prompt_text: str) -> str:
        """Custom prompt without the SREArena> prefix"""
        loop = asyncio.get_running_loop()
        style = Style.from_dict({"prompt": "ansiblue"})
        prompt_txt = [("class:prompt", prompt_text)]
        with patch_stdout():
            try:
                return await loop.run_in_executor(
                    None,
                    lambda: self.session.prompt(prompt_txt, style=style, completer=None),
                )
            except (KeyboardInterrupt, EOFError):
                sys.exit(0)

async def main():
    conductor = Conductor()
    agent = HumanAgent(conductor)
    conductor.register_agent()  # no-op but for symmetry

    # 1) Intro & pick a problem
    agent.display_welcome()
    await agent.select_mode()

    configure = await agent._prompt_with_default("Configure transient issues now? (y/n)", "n")
    if configure.lower() in ['y', 'yes']:
        await agent.configure_transient_issues()

    # 2) Deploy environment & launch HTTP server
    await conductor.start_problem()

    # 3) Interactive shell / submit loop
    await agent.interactive_loop()


if __name__ == "__main__":
    asyncio.run(main())
