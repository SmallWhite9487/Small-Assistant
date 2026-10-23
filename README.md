# Small-Assistant

Small-Assistant is a desktop Japanese-learning companion built with Python and
Tkinter. It keeps a personal vocabulary list in a local CSV file and provides
tools to practise and improve Japanese.

## Features

- Add, edit, search, and remove vocabulary entries.
- Review saved words as flashcards.
- Read Japanese text in kana.
- Check Japanese grammar with an AI provider.
- Check flagged vocabulary entries for word information and suggested fixes.

## Requirements

- Python 3.10 or later
- A Gemini API key for the AI-powered grammar and vocabulary checks

## Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/SmallWhite9487/Small-Assistant.git
   cd Small-Assistant
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env`, then set `GEMINI_API_KEY`:

   ```env
   GEMINI_API_KEY=your_api_key_here
   ```

5. Start the application:

   ```bash
   python main.py
   ```

`words.csv` is the local vocabulary database. It is included with sample or
existing personal entries and is updated by the application.

## Updating the project

On Windows, `pull.cmd` pulls the latest changes, prompts for a commit message,
then pushes your update. Review staged files before committing to ensure
personal data and secrets are not included.

## Privacy

The `.env` file is ignored by Git and must not be committed. Grammar and word
checks send the text being checked to the configured AI provider.

## License

This project is available under the [MIT License](LICENSE).
