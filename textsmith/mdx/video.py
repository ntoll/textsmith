"""
Randomly downloaded as a script from the internet. Probably flakey.

Supports the responsive embedding of web videos URLs (currently YouTube and
Vimeo are supported) using the flex-video method.  Flex-video provides an
 intrinsic ratio that will properly scale your video on any device.
"""
import markdown

from markdown.util import etree

version = "0.0.1"


class VideoExtension(markdown.Extension):
    def __init__(self, configs=None):
        for k, v in configs or {}:
            self.setConfig(k, v)

    def add_inline(self, md, name, klass, re):
        pattern = klass(re)
        pattern.md = md
        pattern.ext = self
        md.inlinePatterns.add(name, pattern, "<reference")

    def extendMarkdown(self, md, md_globals):
        self.add_inline(
            md,
            "vimeo",
            Vimeo,
            r"([^(]|^)(http|https)://(www.|)vimeo\.com/(?P<vimeoid>\d+)\S*",
        )
        self.add_inline(
            md,
            "youtube",
            Youtube,
            r"([^(]|^)(http|https)://www\.youtube\.com/watch\?\S*v=(?P<youtubeargs>[A-Za-z0-9_&=-]+)\S*",  # noqa
        )


class Vimeo(markdown.inlinepatterns.Pattern):
    def handleMatch(self, m):
        url = (
            "https://player.vimeo.com/video/%s?byline=0&amp;portrait=0"
            % m.group("vimeoid")
        )
        width = "560"
        height = "315"
        return flex_video(url, width, height)


class Youtube(markdown.inlinepatterns.Pattern):
    def handleMatch(self, m):
        url = "https://www.youtube-nocookie.com/embed/%s" % m.group(
            "youtubeargs"
        )
        width = "560"
        height = "315"
        return flex_video(url, width, height)


def flex_video(url, width, height):
    obj = etree.Element("div")
    obj.set("class", "flex-video")
    iframe = etree.Element("iframe")
    iframe.set("width", width)
    iframe.set("height", height)
    iframe.set("src", url)
    iframe.set("frameborder", "0")
    obj.append(iframe)
    return obj


def makeExtension(configs=None):
    return VideoExtension(configs=configs)
