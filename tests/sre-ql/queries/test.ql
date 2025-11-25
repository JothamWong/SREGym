/**
 * @kind problem
 * @id sre-ql.python-find-functions
 * @name Find Python functions
 * @description Lists all Python functions in the codebase.
 */

import python

from Function f
select f, "Function defined here."


