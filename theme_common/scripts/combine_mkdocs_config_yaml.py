import yaml
import sys

def merge_yaml_files(file1, file2, output_file):

    with open(file1, 'r') as f1, open(file2, 'r') as f2:
        data1 = yaml.load(f1, Loader=yaml.Loader)
        data2 = yaml.load(f2, Loader=yaml.Loader)
        merged_data = merge_dicts(data1, data2)

    with open(output_file, 'w') as out_file:
        yaml.dump(merged_data, out_file, default_flow_style=False)

def merge_dicts(dict1, dict2):
    for key in dict2:
        if key in dict1:
            if isinstance(dict1[key], dict) and isinstance(dict2[key], dict):
                merge_dicts(dict1[key], dict2[key])
            elif isinstance(dict1[key], list) and isinstance(dict2[key], list):
                dict1[key] = merge_lists(dict1[key], dict2[key])
            else:
                dict1[key] = dict2[key]
        else:
            dict1[key] = dict2[key]
    return dict1

def merge_lists(list1, list2):
    merged_list = list1[:]
    for item in list2:
        if item not in merged_list:
            merged_list.append(item)
    return merged_list

if __name__ == "__main__":

    if len(sys.argv) != 4:
        print("Usage: python combine_mkdocs_config_yaml.py <common_mkdocs_file_path> <override_mkdocs_file_path> <output_path>")
        sys.exit(1)
    common_mkdocs_file_path = sys.argv[1]
    override_mkdocs_file_path = sys.argv[2]
    output_path = sys.argv[3]

    merge_yaml_files(common_mkdocs_file_path, override_mkdocs_file_path, output_path)
    print(f"YAML files merged successfully. Merged file saved at {output_path}")
