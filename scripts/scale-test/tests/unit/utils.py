from benchmarklib.models import ClusterInfo, Unit

ID_COUNTER = 0


def get_new_id():
    global ID_COUNTER

    id = ID_COUNTER
    ID_COUNTER += 1
    return id


def get_unit(instance_id=None, ip=None, name=None):
    id = get_new_id()
    instance_id = instance_id or f"instance_{id}"
    ip = ip or f"ip_{id}"
    name = name or f"name_{id}"
    return Unit(instance_id=instance_id, ip=ip, name=name)


def get_cluster_info(
    model="model", app="app", master=None, control_plane=None, workers=None
):
    master = master or get_unit()
    control_plane = control_plane or [master]
    workers = workers or []
    return ClusterInfo(
        app=app,
        model=model,
        master=master,
        control_plane=control_plane,
        workers=workers,
    )
