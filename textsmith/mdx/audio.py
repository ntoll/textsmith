"""
Audio tags.
"""
import markdown
from markdown.util import etree


__version__ = "0.1.4"
__author__ = "Panos Kountanis"


class AudioExtension(markdown.Extension):

    pattern = (
        r"(?:(?:^::+)){0}\[(?P<title>[\w\s\d+]*)\]\((?P<urls>[\w\d\W+]*)\)"
    )
    configs = {}

    def __init__(self, configs=None):
        for key, value in configs or {}:
            self.setConfig(key, value)

    def extendMarkdown(self, md, md_globals):
        self._add_inline(
            "audio", self.pattern.format("audio"), AudioPattern, md, md_globals
        )
        self._add_inline(
            "audiojs",
            self.pattern.format("audiojs"),
            AudioPattern,
            md,
            md_globals,
        )

    def _add_inline(self, name, pattern, klass, md, md_globals):
        inline_audio_pattern = klass(pattern)
        inline_audio_pattern.md = md
        inline_audio_pattern.ext = self
        md.inlinePatterns.add(name, inline_audio_pattern, "<reference")


class AudioPattern(markdown.inlinepatterns.Pattern):
    def handleMatch(self, m):
        audio = etree.Element("audio")
        audio.set("controls", "controls")

        audio_urls = m.group("urls")

        for url in audio_urls.replace(",", "").split(" "):
            ext = url.split(".")[-1]
            src = etree.Element("source")
            src.set("src", url.strip())
            src.set("type", "audio/{0}".format(ext))
            audio.append(src)
        return audio


def makeExtension(configs=None):
    return AudioExtension(configs=configs)
