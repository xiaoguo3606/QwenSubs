# QwenSubs

A Chinese-friendly AI subtitle tool. Based on Qwen3-ASR for accurate subtitle generation, supporting speech recognition (ASR) and forced alignment (matching existing text with audio to generate subtitles).

## Features

- 🎤 **Speech Recognition (ASR)** — Convert audio to subtitles with timestamps
- 🎯 **Forced Alignment** — Existing text + audio → word-level timestamped subtitles
- 📝 **Sentence Splitting Editor** — Manually adjust sentence boundaries and text
- 📦 **Multi-format Export** — SRT / ASS / VTT
- 🧠 **LLM Correction** — Optional Ollama / OpenAI-compatible API for correcting proper nouns (names, places, etc.)
- 🎛️ **Punctuation Formatting** — Batch remove punctuation at sentence ends or mid-sentence, auto-capitalize first letter for English subtitles
- ⏱️ **Long Audio Support** — Handles audio over 5 minutes for both recognition and alignment

## Quick Start

### Windows

Double-click `start.bat`. The script will automatically:

1. Check Python environment (download and install if missing)
2. Create a virtual environment
3. Install dependencies
4. Launch the application

### macOS

```bash
chmod +x start.sh
./start.sh
```

### Manual Installation

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

After launching, open http://127.0.0.1:7860 in your browser. First, download the model from the "Settings" page, then you're ready to use the tool.

## Usage

1. **Download Models**: Go to "Settings → Model Management", select a download source (ModelScope / HuggingFace), download the ASR model and alignment model
2. **Speech Recognition**: Upload audio → Select language → Click "Start Recognition" → Adjust sentence splitting in the editor → "Confirm & Generate Subtitles"
3. **Forced Alignment**: Upload audio + paste corresponding text → Click "Start Alignment" → Same workflow as above
4. **LLM Correction (Optional)**: Enable and configure in "Settings → LLM Configuration", supports Ollama or OpenAI-compatible APIs

## Project Structure

```
qwen-asr-srt/
├── app.py                    # Gradio main entry point
├── core/
│   ├── asr_engine.py         # Qwen3ASR wrapper
│   ├── forced_aligner.py     # Qwen3ForcedAligner wrapper
│   ├── audio_processor.py    # Audio format conversion / chunking
│   ├── subtitle_builder.py   # Subtitle file generation (SRT/ASS/VTT)
│   ├── sentence_splitter.py  # Punctuation-based sentence splitting
│   └── punctuation_cleaner.py# Punctuation cleanup
├── ui/
│   ├── asr_tab.py            # ASR page
│   ├── align_tab.py          # Forced alignment page
│   ├── review_editor.py      # Subtitle review & editor
│   └── settings_tab.py       # Settings page
├── config/
│   └── settings.py           # Configuration management
├── utils/
│   ├── hardware_detector.py  # Hardware detection
│   ├── model_manager.py      # Model download management
│   └── llm_client.py         # LLM client
├── i18n.py                   # Internationalization
├── requirements.txt
├── start.bat                 # Windows one-click launcher
└── start.sh                  # macOS/Linux one-click launcher
```

## Roadmap

- [ ] Add English UI support
- [ ] Support more ASR and forced alignment models
- [ ] Package as App / exe
- [ ] Add TTS tooling

## Dependencies

- Python 3.11+
- [qwen-asr](https://pypi.org/project/qwen-asr/) — Qwen3-ASR model
- PyTorch — Deep learning framework
- modelscope / hf-mirror / huggingface_hub — Model download

## License

Apache 2.0
