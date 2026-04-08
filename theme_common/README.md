# `stakater-docs-mkdocs-theme`

This project serves as a shared MkDocs theme for all the Stakater MkDocs projects. By integrating this repository as a git submodule into your project, you can utilize the common theme and take updates.

## Usage Guide

### Pre-requisites

Python 3 environment

### 1. Import as git submodule

Add this repo as a submodule to your target `mkdocs` project at the `theme_common` path:

```sh
git submodule add git@github.com:stakater/stakater-docs-mkdocs-theme.git theme_common
```

Your target project directory should look like this after adding the submodule:

```txt
your-project/
    theme_common/
    ...
```

You can learn more about git submodules [here](https://git-scm.com/book/en/v2/Git-Tools-Submodules).

### 2. Directory structure in target project

To override the `theme_common`, create a `theme_override` folder and customise the files there as you need. Directory structure would look like this after that:

```txt
your-project/
    theme_common/
    theme_override/
```

In your `theme_override` folder, you could for example override `mkdocs.yml` in the common theme by creating the same file in the `theme_override` folder:

```yaml
site_name: <project name>
site_url: https://project-name.stakater.com/
repo_url: <git https url>
docs_dir: content
edit_uri: blob/main/content/

nav:
  - index.md
```

### 3. Add content in target MkDocs project

In this project, default `mkdocs` documentation folder is set to `content`. If you want to override that setting, you can change following properties in `theme_override/mkdocs.yml`:

- `docs_dir`
- `edit_uri`

Add your content and then you can link it in `theme_override/mkdocs.yml` by overriding the following setting:

- `nav`

You can visit `mkdocs` official documentation to find out how to define `nav` in `mkdocs.yml` file.

Target project's directory structure would look like this after adding `content` dir:

```txt
your-project/
    theme_common/
    theme_override/
    content/
```

### 4. Run scripts in target project

Assuming that target project will already have a python environment,
execute the following commands in the root of your target project:

1. Install Python Dependencies:

   ```bash
   pip3 install -r theme_common/requirements.txt
   ```

1. Combine Theme Resources:

   ```bash
   python theme_common/scripts/combine_theme_resources.py theme_common/resources theme_override/resources dist/_theme
   ```

   > Above command will output combined theme to `dist/_theme`.

1. Produce `mkdocs` YAML file:

   ```bash
   python theme_common/scripts/combine_mkdocs_config_yaml.py theme_common/mkdocs.yml theme_override/mkdocs.yml mkdocs.yml
   ```

   > These scripts will create a combined theme and a `mkdocs.yml` file.

Your target project will now have an `mkdocs` theme. If you want to customise `mkdocs.yml` or theme resources, you can do so by modifying files in `theme_override` folder and running the above scripts again.

Your Dockerfile in the target repo needs to run the same steps to build the combined theme that will be used to build the docs.

Versioning is provided by `theme_override` and can be added to the `mkdocs.yml` when required under:

```extra:
    version:
        provider: mike
        default: latest
```

It is compiled under the `dist/_theme`

> [!NOTE]
> Copy the [`prepare_theme.sh`](./prepare_theme.sh) file to your project and run it to avoid having to remember to run all commands in step 4.
>
> [!NOTE]
> Use the [`prepare_theme_pr.sh`](./prepare_theme_pr.sh) in your pull request builds to generate pull request specific overrides.
