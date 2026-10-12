"""Convert the project's standalone report markup to portable Markdown.

Uses only the standard library. Headings, tables, links, images and code are
preserved; navigation and CSS are presentation scaffolding and are omitted.
"""
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse
import os
import re


@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)


class ReportParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('root')
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in {'br', 'img', 'meta', 'link', 'hr', 'input'}:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, dict(attrs)))

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def plain(node):
    return node if isinstance(node, str) else ''.join(plain(c) for c in node.children)


def html_to_markdown(source, output_path):
    output_path = Path(output_path).resolve()
    parser = ReportParser()
    parser.feed(source)

    def target(value):
        if value.startswith('file:'):
            path = unquote(urlparse(value).path)
            if re.match(r'^/[A-Za-z]:/', path): path = path[1:]
            value = os.path.relpath(Path(path), output_path.parent).replace('\\', '/')
        if value.endswith('.html') and not value.startswith(('http:', 'https:')):
            value = value[:-5] + '.md'
        return '<'+value+'>' if any(c.isspace() for c in value) else value

    def inline(node):
        if isinstance(node, str):
            value = re.sub(r'\s+', ' ', node)
            return value.replace('\\', '\\\\').replace('[', '\\[').replace(']', '\\]')
        text = ''.join(inline(c) for c in node.children)
        if node.tag in {'strong','b'}: return '**'+text+'**'
        if node.tag in {'em','i'}: return '*'+text+'*'
        if node.tag == 'code':
            raw = plain(node)
            fence = '``' if '`' in raw else '`'
            return fence + raw + fence
        if node.tag == 'a': return '['+text+']('+target(node.attrs.get('href',''))+')'
        if node.tag == 'img': return '!['+node.attrs.get('alt','')+']('+target(node.attrs.get('src',''))+')'
        if node.tag == 'br': return '  \n'
        return text

    def block(node):
        if isinstance(node,str): return inline(node)
        if node.tag in {'head','style','script','nav'}: return ''
        if re.fullmatch(r'h[1-6]',node.tag): return '#' * int(node.tag[1])+' '+inline(node).strip()+'\n\n'
        if node.tag in {'p','figcaption'}: return inline(node).strip()+'\n\n'
        if node.tag == 'br': return '\n'
        if node.tag == 'pre':
            code = plain(node).strip('\n')
            language = 'powershell' if any(s in code for s in ['Set-Location','$isaacPython','Get-Content']) else 'python'
            return '```'+language+'\n'+code+'\n```\n\n'
        if node.tag == 'table':
            rows=[]
            def visit(item):
                if isinstance(item,str): return
                if item.tag=='tr':
                    rows.append([inline(c).strip().replace('|','\\|').replace('\n','；') for c in item.children if isinstance(c,Node) and c.tag in {'td','th'}])
                else:
                    for child in item.children:visit(child)
            visit(node)
            if not rows:return ''
            width=max(map(len,rows));rows=[row+['']*(width-len(row)) for row in rows]
            lines=['| '+' | '.join(rows[0])+' |','| '+' | '.join(['---']*width)+' |']
            lines += ['| '+' | '.join(row)+' |' for row in rows[1:]]
            return '\n'.join(lines)+'\n\n'
        if node.tag == 'blockquote':
            text=''.join(block(c) for c in node.children).strip()
            return '\n'.join('> '+line for line in text.splitlines())+'\n\n'
        if node.tag=='img':return inline(node)+'\n\n'
        if node.tag in {'ul','ol'}:
            items=[c for c in node.children if isinstance(c,Node) and c.tag=='li']
            return '\n'.join((str(i+1)+'. ' if node.tag=='ol' else '- ')+inline(c).strip() for i,c in enumerate(items))+'\n\n'
        text=''.join(block(c) for c in node.children)
        return text+'\n\n' if node.tag in {'section','footer','figure','div'} else text

    result=block(parser.root)
    result=re.sub(r'\n{3,}','\n\n',result).strip()+'\n'
    return result
