import python

class ProblemSubclass extends ClassValue {
  ProblemSubclass() {
    this.getASuperType().getName() = "Problem"
  }
  
  ClassValue getTheClass() { result = this }
}

class SelfAppAssignment extends AssignStmt {
  SelfAppAssignment() {
    exists(Attribute attr |
      attr = this.getATarget() and 
      attr.getObject().(Name).getId() = "self" and
      attr.getName() = "app"
    )
  }
  
  predicate isNoneAssignment() {
    this.getValue() instanceof None
  }
  
  predicate isInInit() {
    this.getScope().(Function).getName() = "__init__"
  }
}

predicate hasValidAppAssignment(ClassValue c) {
  exists(SelfAppAssignment a |
    a.getScope().getScope() = c and
    a.isInInit() and
    not a.isNoneAssignment()
  )
}

predicate hasNoneAppAssignment(ClassValue c) {
  exists(SelfAppAssignment a |
    a.getScope().getScope() = c and
    a.isInInit() and
    a.isNoneAssignment()
  )
}

from ProblemSubclass prob, string message
where
  (not hasValidAppAssignment(prob.getTheClass()) and 
   not hasNoneAppAssignment(prob.getTheClass()) and
   message = "Problem subclass missing self.app assignment in __init__")
  or
  (hasNoneAppAssignment(prob.getTheClass()) and
   message = "Problem subclass assigns None to self.app in __init__")
select prob.getTheClass(), message