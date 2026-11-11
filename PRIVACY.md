# Privacy and data flow

This document describes the code in this repository. A self-hosted instance's operator controls its deployment, logging, endpoint configuration, and access. It is not a promise about the public bot or a third-party deployment.

## What is sent

1. Telegram delivers a command, message text, chat metadata, user ID, and available language code to the bot.
2. For `/ask`, the bot sends the question and configured system instruction to the selected provider's `api_url`, along with the configured model parameters and API key.
3. The provider's answer is sent back through Telegram to the originating chat. In a group, other participants can see it.

The request payload does not explicitly include the Telegram user ID, username, or chat ID. Any identifying information typed into the question is still sent. Providers see the bot host's network address. A custom gateway receives the same content and key as a direct provider endpoint.

## Storage and logs

- There is no conversation database or persisted chat history. Each question is independent.
- The application retains user IDs and timestamps in memory for cooldown enforcement. Expired entries are removed when the next nonempty question is processed; stopping the process also clears them.
- Telegram updates and request/response data exist in process memory while handled. Framework internals may retain operational metadata.
- Application logs record startup, configuration failure categories, and request failure categories, not full prompts, answers, or keys. HTTP client INFO/DEBUG logs are suppressed by the normal entry point.
- The code does not add analytics, browser cookies, or localStorage.

Hosting providers, reverse proxies, custom logging, Telegram, and LLM providers can have their own storage and retention policies. This application cannot erase their copies or guarantee their retention periods.

## Your choices

Do not submit secrets or sensitive personal information unless you understand and accept the policies of Telegram, the operator, and the configured provider. Review the [Telegram privacy policy](https://telegram.org/privacy), [OpenAI privacy policy](https://openai.com/policies/privacy-policy/), or [xAI privacy policy](https://x.ai/legal/privacy-policy), as applicable.

Contact the instance operator for access, deletion, or deployment-specific privacy questions. Deleting a Telegram message or restarting the bot does not necessarily remove provider-side copies. Repository maintainers do not administer independently hosted instances.

For accidental credential disclosure or vulnerabilities, see [SECURITY.md](SECURITY.md).
