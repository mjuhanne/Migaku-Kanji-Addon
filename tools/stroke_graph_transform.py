import svg_path_transform as S
from bs4 import BeautifulSoup
from decimal import Decimal
import os
import argparse

from html.parser import HTMLParser
from html import escape

xml_header = '<?xml version="1.0" encoding="UTF-8"?>\n'
svg_header = \
    '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.0//EN" "http://www.w3.org/TR/2001/REC-SVG-20010904/DTD/svg10.dtd" [\n' + \
    '<!ATTLIST g\n' + \
    'xmlns:kvg CDATA #FIXED "http://kanjivg.tagaini.net"\n' + \
    'kvg:element CDATA #IMPLIED\n' + \
    'kvg:variant CDATA #IMPLIED\n' +\
    'kvg:partial CDATA #IMPLIED\n' +\
    'kvg:original CDATA #IMPLIED\n' +\
    'kvg:part CDATA #IMPLIED\n' +\
    'kvg:number CDATA #IMPLIED\n' +\
    'kvg:tradForm CDATA #IMPLIED\n' +\
    'kvg:radicalForm CDATA #IMPLIED\n' +\
    'kvg:position CDATA #IMPLIED\n' +\
    'kvg:radical CDATA #IMPLIED\n' +\
    'kvg:phon CDATA #IMPLIED >\n' +\
    '<!ATTLIST path\n' +\
    'xmlns:kvg CDATA #FIXED "http://kanjivg.tagaini.net"\n' +\
    'kvg:type CDATA #IMPLIED >\n' +\
    ']>\n';

class MyHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.__t = 0
        self.lines = []
        self.__current_line = ''
        self.__current_tag = ''
        self.__indent = 0

    @staticmethod
    def __attr_str(attrs):
        return ' '.join('{}="{}"'.format(name, escape(value)) for (name, value) in attrs)

    def handle_starttag(self, tag, attrs):
        #if tag != self.__current_tag:
        self.lines += [self.__current_line]

        self.__current_line = '\t' * self.__t + '<{}>'.format(tag + (' ' + self.__attr_str(attrs) if attrs else ''))
        self.__current_tag = tag
        self.__t += 1

    def handle_endtag(self, tag):
        self.__t -= 1
        if tag != self.__current_tag:
            self.lines += [self.__current_line]
            self.lines += ['\t' * self.__t + '</{}>'.format(tag)]
        else:
            self.lines += [self.__current_line + '</{}>'.format(tag)]

        self.__current_line = ''

    def handle_data(self, data):
        self.__current_line += data

    def get_parsed_string(self):
        return '\n'.join(l for l in self.lines if l)



def path_to_string(data, sfig=5, ndig=None, sep=' '):
    def to_string(v):
        if isinstance(v, float):
            s =  _to_significant_figures_and_digits(v, sfig, ndig)
        else:
            s = str(v)
        return s

    data = [[cmd[0], *[v for vs in cmd[1:] for v in vs]] for cmd in data]
    ps = '  '.join(to_string(v) for vs in data for v in vs)
    i = 0
    digits = ['0','1','2','3','4','5','6','7','8','9']
    prev_char = None
    new_ps = ''
    for i in range(len(ps)):
        p = ps[i]
        if p == ' ':
            if prev_char in digits and (i+1 < len(ps)) and (ps[i+1] in digits):
                new_ps = new_ps + ','
        else:
            new_ps = new_ps + p
            prev_char = p
    return new_ps


def _to_significant_figures_and_digits(v: float, n_figures: int, n_digits: int) -> str:
    n_digits = float('inf') if n_digits is None else n_digits
    d = Decimal(v)
    d = d.quantize(Decimal((0, (), max(d.adjusted() - n_figures + 1, -n_digits))))
    return str(d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize())

convert_kanji_list = []

def transform_svg_file(svg_filename,svg_path,output_file, x_ofs, y_ofs, x_scale, y_scale):

    try:
        with open(svg_path,"r",encoding="utf-8") as fi:
                lines = [line.rstrip() for line in fi]
        if '<!--' in lines[0]:
            lines = lines[1:]
        contents = '\n'.join(lines)
        if '<?xml' != contents[:len('<?xml')]:
            contents = xml_header + svg_header + contents
        #lines[0] = svg_header
        soup = BeautifulSoup(contents,"xml")

        svg_tag = soup.find("svg")

        # fix ID numbering
        g_elements = soup.find_all("g")
        g_id_base_name = g_elements[1]['id']
        kanji = g_elements[1]['kvg:element']
        convert_kanji_list.append(kanji)
        idx = -1
        for g in g_elements:
            if idx >= 1 and 'StrokeNumbers' not in g['id']:
                g['id'] = g_id_base_name + '-g' + str(idx)
                pass
            idx += 1

        # fix stupidness
        #g_elements[-1]['id'] = 'kvg:StrokeNumbers_' + g_id_base_name.split(':')[1]


        print("%s (%s): X ofs %.2f Y ofs %.2f x_scale %.2f y_scale %.2f" % (kanji, svg_filename, x_ofs,y_ofs,x_scale,y_scale))
    except:
        print("ERROR opening file %s" % svg_path)
        return

    # transform paths and fix Id numbering
    paths = soup.find_all("path")
    idx = 1
    for p in paths:
        p['id'] = g_id_base_name + '-s' + str(idx)
        idx += 1

        d = p['d']
        p2 = S.parse_path(d)
        new_d = S.translate_and_scale(p2,  s=(x_scale, y_scale), t=(x_ofs, y_ofs))
        new_d_str = path_to_string(new_d, sfig=3, sep=' ')
        p['d'] = new_d_str

    # transform stroke number text
    text = soup.find_all("text")
    for t in text:
        tr = t['transform'].split(' ')
        x = float(tr[4])
        y_str = tr[5][:-1]
        y = float(y_str)
        x = x*x_scale + x_ofs
        y = y*y_scale + y_ofs
        tr[4] = _to_significant_figures_and_digits(x, 3, None)
        tr[5] = _to_significant_figures_and_digits(y, 3, None) + ')'
        t['transform'] = ' '.join(tr)
        

    #new_content = soup.prettify(formatter=) #str(soup)
    str_soup = str(soup)
    str_soup = str_soup.replace('\n','')
    parser = MyHTMLParser()
    parser.feed(str_soup)
    new_content = parser.get_parsed_string()

    # fix stupidness vol #2
    """
    new_content = new_content.replace(' element=',' kvg:element=')
    new_content = new_content.replace(' variant=',' kvg:variant=')
    new_content = new_content.replace(' type=',' kvg:type=')
    new_content = new_content.replace(' position=',' kvg:position=')
    new_content = new_content.replace(' phon=',' kvg:phon=')
    """
    new_content = new_content.replace(' radical=',' kvg:radical=')
    new_content = new_content.replace(' original=',' kvg:original=')

    # strip headers
    new_content = new_content.replace(xml_header,'')
    new_content = new_content.replace(svg_header,'')

    with open(output_file,"w",encoding="utf-8") as of:
        of.write(new_content)


parser = argparse.ArgumentParser(prog=__package__, description='SVG path data transformer')
arg = parser.add_argument
arg('--dx', metavar='N', type=float, default=0., help='translate x by N')
arg('--dy', metavar='N', type=float, default=0., help='translate y by N')
arg('--sx', metavar='N', type=float, default=1., help='scale x by N')
arg('--sy', metavar='N', type=float, default=1., help='scale y by N')
arg('--src', metavar='N', type=str, default="", help='Source file')
arg('--dest', metavar='N', type=str, default="", help='Destination file')
arg('--kanji', '-k', type=str, default="", help='Kanji')
arg('--path', metavar='N', type=str, default="addon/kanjivg-supplementary", help='Kanji')
args = parser.parse_args()

args.path = 'migaku/addon/kanjivg-supplementary'
#args.kanji = "quarter"
args.kanji = "ALL"

if args.path[-1] != '/':
    args.path = args.path + '/'

if args.src == '':
    if args.kanji == '':
        print("Source file and kanji both cannot be empty!")
        exit(0)
    else:
        if len(args.kanji) == 1:
            src_path = args.path + "%05x.svg" % ord(args.kanji)
        else:
            src_path = args.path + args.kanji + '.svg'
else:
    src_path = args.src
svg_filename = src_path.split('/')[-1]

if args.dest == '':
    dest_path = src_path
else:
    dest_path = args.dest

if args.kanji == 'ALL':
    file_list = os.listdir(args.path)
    for fn in file_list:
        src_path = args.path + fn
        dest_path = src_path
        svg_filename = src_path.split('/')[-1]
        transform_svg_file(svg_filename, src_path, dest_path, args.dx, args.dy, args.sx, args.sy)
else:
    transform_svg_file(svg_filename, src_path, dest_path, args.dx, args.dy, args.sx, args.sy)

print("Converted:")
convert_kanji_list_2 = [ '[' + x + ']' if len(x)> 1 else x for x in convert_kanji_list]
print(''.join(convert_kanji_list_2))
#print(','.join(convert_kanji_list))