# -*- coding: utf-8 -*-
"""Doubao Seedream Image Generator — QwenPaw Plugin Entry Point."""
import importlib.util
import logging
import os

from qwenpaw.plugins.api import PluginApi

logger = logging.getLogger(__name__)


class DoubaoSeedreamImagePlugin:
    """Register the generate_image tool into QwenPaw Agent toolkit."""

    def register(self, api: PluginApi) -> None:
        """Register plugin via startup hook."""
        api.register_startup_hook(
            hook_name="register_doubao_seedream_tool",
            callback=self._register_tool,
            priority=50,
        )
        logger.info("Doubao Seedream image plugin registered")

    def _register_tool(self) -> None:
        """Load tool.py and inject generate_image into agent toolkit."""
        try:
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            tool_path = os.path.join(plugin_dir, "tool.py")
            spec = importlib.util.spec_from_file_location(
                "doubao_seedream_tool", tool_path,
            )
            if spec is None or spec.loader is None:
                logger.error("Cannot load tool module from %s", tool_path)
                return
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Register globally
            import qwenpaw.agents.tools as tools_module
            setattr(tools_module, "generate_image", module.generate_image)
            _all = getattr(tools_module, "__all__", None)
            if _all is not None and "generate_image" not in _all:
                _all.append("generate_image")
            logger.info("Registered tool: generate_image")

            # Add to agent config
            self._add_to_agent_config()

        except Exception:
            logger.exception("Failed to register generate_image tool")

    @staticmethod
    def _add_to_agent_config() -> None:
        """Ensure generate_image appears in the current agent's tool config."""
        try:
            from qwenpaw.app.agent_context import get_current_agent_id
            from qwenpaw.config.config import (
                BuiltinToolConfig,
                ToolsConfig,
                load_agent_config,
                save_agent_config,
            )

            agent_id = get_current_agent_id()
            if not agent_id:
                return

            cfg = load_agent_config(agent_id)
            if not cfg.tools:
                cfg.tools = ToolsConfig()

            tool_name = "generate_image"
            for t in cfg.tools.builtin_tools or []:
                if t.name == tool_name:
                    return  # already present

            new_tool = BuiltinToolConfig(
                name=tool_name,
                enabled=True,
                description="调用豆包 Seedream 等文生图模型生成图片",
            )
            if cfg.tools.builtin_tools is None:
                cfg.tools.builtin_tools = []
            cfg.tools.builtin_tools.append(new_tool)
            save_agent_config(agent_id, cfg)
            logger.info("Added %s to agent %s config", tool_name, agent_id)

        except Exception:
            logger.debug("Could not add tool to agent config", exc_info=True)


# QwenPaw requires plugin.py to export a 'plugin' object
plugin = DoubaoSeedreamImagePlugin()
