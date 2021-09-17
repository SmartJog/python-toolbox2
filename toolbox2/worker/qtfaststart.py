from toolbox2.worker import Worker, WorkerException


class QtFastStartWorkerException(WorkerException):
    pass


class QtFastStartWorker(Worker):
    def __init__(self, log, params=None):
        Worker.__init__(self, log, params)
        self.tool = "qt-faststart"

    def add_input_file(self, path, params=None):
        if len(self.input_files) > 0:
            raise QtFastStartWorkerException("qt-faststart only support one input file")
        Worker.add_input_file(self, path, params)

    def add_output_file(self, path, params=None):
        if len(self.output_files) > 0:
            raise QtFastStartWorkerException("qt-faststart only support one input file")
        Worker.add_output_file(self, path, params)

    def get_args(self):
        args = Worker.get_args(self)

        for input_file in self.input_files:
            args += input_file.get_args()

        for output_file in self.output_files:
            args += output_file.get_args()

        return args
