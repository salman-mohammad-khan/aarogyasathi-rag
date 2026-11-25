"""Prompt-injection guard.

A message that tries to change the bot's role, rules or output, to read its prompt or keys, or to switch the safety
rules off, gets a fixed reply. No model is called for it, so a clever wording cannot talk its way through.
Plain word patterns in English, Hinglish and Hindi; like the emergency rules they cannot understand a message, they only
match wordings listed here. The model prompts add a second layer (see generator.py).
"""
import re

_FLAGS = re.IGNORECASE

_PATTERNS = [
    # "ignore all previous instructions", "forget your rules", "disregard the above guidelines"
    r"\b(ignore|disregard|forget|override|bypass|skip)\b[^.?!\n]{0,40}\b(previous|prior|above|earlier|all|your|these|those|any|the)\b[^.?!\n]{0,30}\b(instructions?|rules?|prompts?|guidelines?|restrictions?|filters?|safety|programming)\b",
    # reading the hidden prompt
    r"\b(system|developer|hidden|initial|original)\s+(prompt|message|instructions?)\b",
    r"\b(reveal|show|print|display|repeat|leak|dump|share)\b[^.?!\n]{0,30}\b(your|the)\b[^.?!\n]{0,20}\b(prompt|instructions?|rules|configuration|settings)\b",
    # keys and secrets
    r"\bapi[ _-]?keys?\b",
    r"\b(bearer|access|secret|admin|auth)[ _-]?(token|key)s?\b",
    r"\b(password|credentials?)\b[^.?!\n]{0,20}\b(of|for|to)\b[^.?!\n]{0,15}\b(server|admin|database|bot|system)\b",
    r"\baws[ _-]?(secret|access|credential)",
    r"\badmin_token\b",
    # role changes and jailbreaks
    r"\byou are now\b",
    r"\bfrom now on[, ]+you\b",
    r"\bpretend (to be|you are|you're|that you)\b",
    r"\bact as (if|though|an? (?!doctor|nurse|health))",
    r"\b(developer|god|jailbreak|unrestricted|dan) mode\b",
    r"\bjailbreak\b",
    r"\bdo anything now\b",
    r"\b(without|no|disable|turn off|remove|drop)\b[^.?!\n]{0,15}\b(safety|rules|restrictions|filters|guidelines|guardrails)\b",
    # forcing output
    r"\b(end|finish|start|begin|conclude)\s+(your|the)\s+(answer|reply|response|message|output)\s+with\b",
    r"\brepeat after me\b",
    r"\bsay\s+['\"“]?\s*i have been\b",
    r"\bi have been (hacked|pwned)\b",
    # Hinglish
    r"\b(pichle|purane|saare|sabhi|apne)\b[^.?!\n]{0,20}\b(nirdesh|instructions?|niyam|rules)\b[^.?!\n]{0,20}\b(bhool|ignore|mat mano|todo|hata)",
    r"\bapne niyam (bhool|todo|hata)",
    r"\bsystem prompt\b",
    # Devanagari
    r"(पिछले|सभी|अपने)\s*(निर्देश|नियम)[^।?!\n]{0,20}(भूल|अनदेखा|नज़रअंदाज़|तोड़|हटा)",
    r"सिस्टम\s*प्रॉम्प्ट",
    r"(एपीआई|API)\s*(की|कुंजी|key)",
]
_COMPILED = [re.compile(p, _FLAGS) for p in _PATTERNS]
_DAN = re.compile(r"\bDAN\b")  # upper case only, so the Indian name Dan is not caught


def _normalise(text):
    return (text or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')


def is_injection(text):
    """True when the message tries to override the bot's rules, read its prompt or keys, or force its output."""
    t = _normalise(text)
    if _DAN.search(t):
        return True
    return any(p.search(t) for p in _COMPILED)
