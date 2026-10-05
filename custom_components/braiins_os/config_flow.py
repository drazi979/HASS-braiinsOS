"""Config, re-auth and options flows for Braiins OS."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_SCAN_INTERVAL, CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import BraiinsApiError, BraiinsAuthError, BraiinsClient
from .const import CONF_POWER_MAX, CONF_POWER_MIN, DEFAULT_SCAN_INTERVAL, DOMAIN


PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


class BraiinsConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return BraiinsOptionsFlow()

    async def _check(self, host, port, username, password) -> str | None:
        client = BraiinsClient(async_get_clientsession(self.hass), host, port, username, password)
        try:
            await client.request("GET", "miner/details")
        except BraiinsAuthError:
            return "invalid_auth"
        except BraiinsApiError:
            return "cannot_connect"
        return None

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            user_input.setdefault(CONF_PASSWORD, "")
            error = await self._check(
                user_input[CONF_HOST], user_input[CONF_PORT],
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD],
            )
            if error is None:
                return self.async_create_entry(
                    title=f"Braiins OS {user_input[CONF_HOST]}", data=user_input
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=80): int,
                vol.Required(CONF_USERNAME, default="root"): str,
                vol.Optional(CONF_PASSWORD, default=""): PASSWORD,
            }),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None) -> ConfigFlowResult:
        """Change host/port/credentials (e.g. after the miner got a new IP)."""
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            user_input.setdefault(CONF_PASSWORD, "")
            error = await self._check(
                user_input[CONF_HOST], user_input[CONF_PORT],
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD],
            )
            if error is None:
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input, title=f"Braiins OS {user_input[CONF_HOST]}"
                )
            errors["base"] = error
        cur = entry.data
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default=cur[CONF_HOST]): str,
                vol.Required(CONF_PORT, default=cur[CONF_PORT]): int,
                vol.Required(CONF_USERNAME, default=cur[CONF_USERNAME]): str,
                vol.Optional(CONF_PASSWORD, default=cur[CONF_PASSWORD]): PASSWORD,
            }),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors = {}
        if user_input is not None:
            error = await self._check(
                entry.data[CONF_HOST], entry.data[CONF_PORT],
                entry.data[CONF_USERNAME], user_input[CONF_PASSWORD],
            )
            if error is None:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Optional(CONF_PASSWORD, default=""): PASSWORD}),
            errors=errors,
        )


class BraiinsOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        errors = {}
        opts = self.config_entry.options
        if user_input is not None:
            lo, hi = user_input.get(CONF_POWER_MIN), user_input.get(CONF_POWER_MAX)
            if lo is not None and hi is not None and lo >= hi:
                errors["base"] = "range_invalid"
            else:
                return self.async_create_entry(data=user_input)
            opts = user_input
        power = vol.All(vol.Coerce(int), vol.Range(min=100, max=20000))
        schema = {
            vol.Required(
                CONF_SCAN_INTERVAL, default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ): vol.All(int, vol.Range(min=10, max=600)),
            vol.Optional(CONF_POWER_MIN, description={"suggested_value": opts.get(CONF_POWER_MIN)}): power,
            vol.Optional(CONF_POWER_MAX, description={"suggested_value": opts.get(CONF_POWER_MAX)}): power,
        }
        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema), errors=errors)
