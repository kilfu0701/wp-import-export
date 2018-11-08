import os

def create_dirs(output_dir, output_dirs):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for _dir in output_dirs:
        sub_dir = output_dir + '/' + _dir
        if not os.path.exists(sub_dir):
            os.makedirs(sub_dir)
