import argparse

def copyfile(dest_kanji, encoded_name, parent_kanji, parent_encoded_name, input,output):
    fo = open(output,"w",encoding="utf-8")
    with open(input,"r",encoding="utf-8") as fi:
        lines = [line.rstrip().replace(parent_encoded_name,encoded_name) for line in fi]
        l2 = f'<g id="kvg:StrokePaths_%s" style="fill:none;stroke:#000000;stroke-width:3;stroke-linecap:round;stroke-linejoin:round;">' % encoded_name
        l3 = f'<g id="kvg:%s" kvg:element="%s">' % (encoded_name,dest_kanji)
        lines[1] = l2
        lines[2] = l3
        data = '<!-- Targeting %s from original %s -->\n' % (dest_kanji,parent_kanji)

        fo.write(data)
        data = '\n'.join(lines)
        fo.write(data)
    fo.close()


parser = argparse.ArgumentParser(prog=__package__, description='SVG stroker order copier')
arg = parser.add_argument
arg('--dest', '-d', type=str, default="", help='Destination kanji name')
arg('--kanji', '-k', type=str, default="", help='Kanji')
arg('--path', metavar='N', type=str, default="addon/kanjivg", help='Source kanji directory')
arg('--dest-path', metavar='N', type=str, default="addon/kanjivg-supplementary", help='Destination kanji directory')
args = parser.parse_args()

print("Args: ",args)
#args.path = 'migaku/addon/kanjivg'
#args.dest_path = 'migaku/addon/kanjivg-supplementary'
#args.kanji = "剥"

if args.path[-1] != '/':
    args.path = args.path + '/'

if args.dest_path[-1] != '/':
    args.dest_path = args.dest_path + '/'

if args.kanji == '':
    print("Kanji cannot be empty!")
    exit(0)

if args.dest == '':
    print("Destination kanji cannot be empty!")
    exit(0)

src_encoded_name = "%05x" % ord(args.kanji)
src_path = args.path + src_encoded_name + ".svg"
svg_filename = src_path.split('/')[-1]

if len(args.dest)==1:
    dest_encoded_name = "%05x" % ord(args.dest)
else:
    dest_encoded_name = args.dest
dest_path = args.dest_path + dest_encoded_name + ".svg"

print("Original file: ", src_path)
print("Destination file: ", dest_path)
copyfile(args.dest, dest_encoded_name, args.kanji, src_encoded_name, src_path, dest_path )
