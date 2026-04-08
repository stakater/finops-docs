import argparse
import os
import shutil

parser = argparse.ArgumentParser()
parser.add_argument('-s', '--source', required=True, help='the source directory path')
parser.add_argument('-ov', '--override', required=True, help='the override from directory path')
parser.add_argument('-o', '--output', required=True, help='the output directory path')
parser.add_argument('-skiprmtree', '--skiprmtree', required=False, action='store_true', help='skip removal of tree when copying submodule')
args = parser.parse_args()

def copy_submodule(source_dir, destination_dir):
    if os.path.exists(destination_dir):
        if args.skiprmtree:
            print(f'Skipping removal of {destination_dir}.')
        else:
            shutil.rmtree(destination_dir)
            print(f'{destination_dir} removed.')
    shutil.copytree(source_dir, destination_dir, dirs_exist_ok=args.skiprmtree)
    print(f'Submodule copied to {destination_dir}.')

def override_resources(theme_override_dir, output_to_dir):
    source_override_dir = theme_override_dir
    destination_override_dir = output_to_dir
    for item in os.listdir(source_override_dir):
        s = os.path.join(source_override_dir, item)
        d = os.path.join(destination_override_dir, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)
    print("Resources overridden.")

if __name__ == "__main__":
    source_dir_path = args.source
    overridefrom_dir_path = args.override
    output_dir_path = args.output
    copy_submodule(source_dir_path,output_dir_path)
    override_resources(overridefrom_dir_path, output_dir_path)
