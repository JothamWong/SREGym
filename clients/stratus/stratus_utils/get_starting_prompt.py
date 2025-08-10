import yaml
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


def get_starting_prompts(config_path):
    with open(config_path, "r") as config_file:
        config = yaml.safe_load(config_file)
        max_step = config["max_step"]
        prompt_file = open(config["prompts_path"], "r")
        prompts = yaml.safe_load(prompt_file)
        sys_prompt = prompts["system"]
        user_prompt = prompts["user"].format(max_step=max_step)
        prompts = []
        if sys_prompt:
            prompts.append(SystemMessage(sys_prompt))
        if user_prompt:
            prompts.append(HumanMessage(user_prompt))

        prompt_file.close()
        return prompts
