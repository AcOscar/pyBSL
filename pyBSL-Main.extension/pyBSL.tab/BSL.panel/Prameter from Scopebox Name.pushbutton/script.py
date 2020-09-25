"""Sets the value of a parameter from rooms to the name of the surrounding Scopebox"""
#pylint: disable=invalid-name,import-error,superfluous-parens
from collections import Counter

from pyrevit import revit, DB
from pyrevit import script
import sys

output = script.get_output()

#Names of the Scopboxes that are used 
namedscopeboxes = ['A','B','C','S']

#parameter to write
parametername = 'Bauteil_Ebene'


if revit.active_view:

    scopeboxes = DB.FilteredElementCollector(revit.doc)\
                 .OfCategory(DB.BuiltInCategory.OST_VolumeOfInterest)

    if scopeboxes.GetElementCount() == 0:
        print('There are no scopeboxes.')
        sys.exit()

    roomids = DB.FilteredElementCollector(revit.doc)\
              .OfCategory(DB.BuiltInCategory.OST_Rooms)\
              .WhereElementIsNotElementType()\
              .ToElementIds()

    if roomids.Count == 0:
        print('There are no rooms.')
        sys.exit()

    for sc in scopeboxes:
        if sc.Name in namedscopeboxes:
            print('\tScopebox: {}'.format(sc.Name.ljust(30)))

            bb = sc.get_BoundingBox(revit.active_view)
            outline = DB.Outline(bb.Min, bb.Max)
            filter = DB.BoundingBoxIsInsideFilter(outline)
            roomcollector = DB.FilteredElementCollector(revit.doc, roomids).WherePasses(filter)

            with revit.Transaction("Set Parameter by Scopebox"):

                for rm in roomcollector:
                        dparam = rm.LookupParameter(parametername)

                        if dparam.StorageType == DB.StorageType.String:
                            #dparam.Set(sc.Name )
                            parametervalue = sc.Name
                            parametervalue += '_'
                            parametervalue += rm.Level.Name.split('_')[1]
                            
                            dparam.Set(parametervalue)

    #                    dparam = rm.LookupParameter('Comments')
    #                    if dparam.StorageType == DB.StorageType.String:
    #                        dparam.Set('')
    #                print(rm.Level.Name.split('_')[1])

print('Done')
