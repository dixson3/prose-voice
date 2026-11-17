def config_for_essay(config: Config, essay: Path) -> Config:
    """The configuration governing one essay.

    An explicit ``--project`` applies to every essay. Otherwise the essay's own nearest Git
    root selects its project, so essays in different projects keep separate project
    configuration and policy; an essay outside any Git repository uses its own directory as
    the project, so its cache sits beside it in ``.prosevoice/cache/``. The derived essay
    directory may not exist yet (``artifacts --apply`` creates it), so it is not validated
    like ``--project``. CLI guidance overrides stay anchored to the invocation directory.
    """
    if config.project_selection == "explicit":
        return config
    essay = (essay if essay.is_absolute() else config.cwd / essay).resolve()
    start = essay.parent
    while not start.is_dir() and start != start.parent:
        start = start.parent  # the essay or its directory may not exist yet
    root = git_root(start)
    how = "essay-git" if root is not None else "essay-dir"
    if root is None:
        root = essay.parent
    if root == config.project_root:
        return config
    project_data = read_config_file(root / PROJECT_DIR / CONFIG_NAME)
    user_data = read_config_file(config.user_config)
    return build_config(config.cwd, root, how, config.user_dir, user_data, project_data,
                        config.overrides, config.env)


# --------------------------------------------------------------------------- guidance
