from IPython.core.magic import Magics, magics_class, line_magic, line_cell_magic, needs_local_scope
from IPython.core.magic_arguments import argument, magic_arguments, parse_argstring
from IPython.display import display, clear_output
from pyspark.sql import SparkSession
from pyspark.sql.dataframe import DataFrame
from string import Formatter
import gc


@magics_class
class VuLeSparkMagic(Magics):

    @magic_arguments()
    @argument('session', metavar='SESSION', type=str, nargs=None, help="Input SparkSession")
    @line_magic
    def register(self, line):
        args = parse_argstring(self.register, line)
        self.spark_session = self.shell.user_ns.get(args.session, None)
        assert isinstance(self.spark_session, SparkSession), "Cannot regiter spark session: {args.session}"
        self._create_temp_view_for_available_dataframe()
    

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
       
        assert self.spark_session is not None, "No registered SparkSession"

        return self.spark_session.read.format(ftype)\
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
            return self.spark_session.sql(query_str)
        else:
            args = parse_argstring(self.sql, line)
            query_str = self._format_params(cell)
            df = self.spark_session.sql(query_str)
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
        _del_after_use = self._find_var_by_name(args.dataframe)
        display(_del_after_use.limit(args.num_rows).toPandas())
        del _del_after_use
        gc.collect()
        clear_output(wait=True)


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

    def _find_var_by_name(self, name):
        """Remember to delete the result when the job done"""
        if not self.shell.user_ns.get(name, None):
            code = name
            try:
                exec("_del_after_use = " + code)
                _del_after_use = self.shell.user_ns['_del_after_use']
                return _del_after_use
            except:
                raise Exception(f"{name} not defined")
    