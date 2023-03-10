from IPython.core.magic import Magics, magics_class, line_magic, line_cell_magic, needs_local_scope
from IPython.core.magic_arguments import argument, magic_arguments, parse_argstring
from IPython.display import display, clear_output
from pyspark.sql import SparkSession
from pyspark.sql.dataframe import DataFrame
from string import Formatter


@magics_class
class VuLeSparkMagic(Magics):

    @property
    def spark(self):
        return SparkSession._instantiatedSession


    @magic_arguments()
    @argument('inputs', metavar='INPUTS', type=str, nargs='+', help="[FILETYPE] [PATH]. FILE_TYPE defaults to `parquet` if not specified")
    @line_magic
    def load_table(self, line):
        """Read Table. Eg: %load_table parquet s3a://bucket/blob/to/file.parquet"""
        args = parse_argstring(self.load_table, line)
        if len(args.inputs) == 1:
            ftype = 'parquet'
            path = args.inputs[0]
        else:
            ftype, path = args.inputs[0], args.inputs[1]
       
        assert self.spark is not None, "No registered SparkSession"

        return self.spark.read.format(ftype)\
                    .option("inferSchema", "true")\
                    .option("header", "true")\
                    .load(path)


    @magic_arguments()
    @argument('dataframe', metavar='DF', type=str, nargs='?')
    @argument('-n', '--num-rows', type=int, default=10)
    @line_cell_magic
    def sql(self, line, cell=None):
        self._create_temp_view_for_available_dataframe()
        if cell is None:
            query_str = self._format_params(line)
            return self.spark.sql(query_str)
        else:
            args = parse_argstring(self.sql, line)
            query_str = self._format_params(cell)
            df = self.spark.sql(query_str)
            if args.dataframe:
                self.shell.user_ns.update({args.dataframe: df})
            else:
                display(df.limit(args.num_rows).toPandas())
       
            clear_output(wait=True)

    @magic_arguments()
    @argument('dataframe', metavar='DF', type=str, nargs=None)
    @argument('-n', '--num-rows', type=int, default=20)
    @line_magic
    def show(self, line):
        args = parse_argstring(self.sql, line)
        df = self.shell.user_ns.get(args.dataframe, None)
        try:
            display(df.limit(args.num_rows).toPandas())
            clear_output(wait=True)
        except AttributeError as err:
            display(err)
            print("Input dataframe is not existed")


    def _create_temp_view_for_available_dataframe(self):
        for k, v in self.shell.user_ns.items():
            v.createOrReplaceTempView(k) if isinstance(v, DataFrame) else None

    def _format_params(self, source):
        params = [fn for _, fn, _, _ in Formatter().parse(source) if fn is not None]
        params_values = {}
        for param in params:
            value = self.shell.user_ns.get(param, None)
            if not value:
                continue
            params_values.update({param: value})
        return source.format(**params_values)
