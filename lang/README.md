# Bot message translations

The bot selects interface text using Telegram's `User.language_code`. Each locale has its own UTF-8 JSON file. These 25 widely used locales are a practical selection, not a population ranking.

| Code | Language |
| --- | --- |
| `ar` | Arabic |
| `bn` | Bengali |
| `de` | German |
| `en` | English |
| `es` | Spanish |
| `fr` | French |
| `hi` | Hindi |
| `id` | Indonesian |
| `it` | Italian |
| `ja` | Japanese |
| `ko` | Korean |
| `mr` | Marathi |
| `nl` | Dutch |
| `pa` | Punjabi (Gurmukhi) |
| `pl` | Polish |
| `pt` | Portuguese |
| `ru` | Russian |
| `ta` | Tamil |
| `te` | Telugu |
| `th` | Thai |
| `tr` | Turkish |
| `ur` | Urdu |
| `vi` | Vietnamese |
| `zh-CN` | Simplified Chinese |
| `zh-TW` | Traditional Chinese |

Regional codes use the base language, such as `pt-BR` -> `pt`. Chinese `Hant`, `TW`, `HK`, and `MO` variants select Traditional Chinese; other Chinese variants select Simplified Chinese. Missing or unsupported codes use English.

The interface language does not force the LLM's response language. Ask the model for the language you want.

## Editing a translation

Keep the keys and placeholders in [en.json](en.json), including `{seconds}`, `{milliseconds}`, `{version}`, `{default}`, and `{providers}`. Command names (including `/providers`) must remain unchanged. Preserve JSON escapes for line breaks and avoid Telegram Markdown/HTML: messages are sent as plain text.

Run `npm run test` after editing. Tests check catalog completeness, matching placeholders, valid formatted messages, Chinese variant routing, and Telegram message lengths. Automated checks do not certify linguistic quality; native-speaker corrections are welcome.

There is no `_locales` directory because this is not a Chrome extension. The [localization module](../localization.py) reads these catalogs directly.
