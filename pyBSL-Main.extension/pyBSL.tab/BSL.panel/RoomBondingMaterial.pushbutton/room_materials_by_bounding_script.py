import clr
clr.AddReference("RevitAPI")
from Autodesk.Revit.DB import FilteredElementCollector as Fec
from Autodesk.Revit.DB import BuiltInCategory as Bic
from Autodesk.Revit.DB import XYZ, UV, AreaVolumeSettings
from Autodesk.Revit.DB import SpatialElementBoundaryOptions, Wall, View3D
from Autodesk.Revit.DB import CheckoutStatus, WorksharingUtils, ReferenceIntersector
from Autodesk.Revit.DB import ElementClassFilter, FindReferenceTarget
from Autodesk.Revit.DB import ShellLayerType, BuiltInParameter
from Autodesk.Revit.DB import SetComparisonResult
from Autodesk.Revit.DB import HostObjectUtils, Face

from System.Diagnostics import Stopwatch

from rpw import db, doc, uidoc
from pyrevit import script, DB, forms

#we need two parameters
#one as length to write the roomheigth
#the second as yes/no to prevent the first one to overwrite it with this script
#so we have the opportunity to write the height value manually

#this is the destination parameter name
room_parameter_name_wall_materials =    "11200 Materialis. Wand/Oberfl."
room_parameter_name_ceiling_materials = "11290 Materialis. Decke/Oberfl."
room_parameter_name_floor_materials =   "11130 Materialis. Bodenbelag"

#this Yes/ No parameter protect a room to overwrite by this script
manual_room_materials_parameter_name = "11xxx Materialis. manuell"

#this is the source parameter name
wall_material_parameter_name = "Typ Bauteilkatalog"

__title__ = 'Wall Materials from bounding Room Faces'

__doc__ = "Runs through all rooms or the preselcted one, and write the materials of the enclosing walls, \n"\
          "and floors into parameters of that room \n"\
          "It will be write into the a parameter.\n"\
          "It requiers this paramters as text paramters on the rooms:\n"\
          "11290 Materialis. Decke/Oberfl.\n"\
          "11200 Materialis. Wand/Oberfl.\n"\
          "11130 Materialis. Bodenbelag\n"\
          "and this as Yes/No Paratmeter:\n"\
          "11xxx Materialis. manuell\n"\
          "and this on the wall and floor elements as source:\n"\
          "Typ Bauteilkatalog"

#set to True for more detailed messages
DEBUG = False
if __shiftclick__:
    DEBUG = True

def param_exists_by_name(any_room, parameter_name):
    return any_room.LookupParameter(parameter_name)


def retrieve_mat_from_room_boundaries(room):

#retrieve the materials from the bounding walls of a room
#it gets room boundary segments and compare the inner and outer face of the touching wall
#if touched we get the material from the face and collect them

    newmat = set()
    loops = room.GetBoundarySegments(SpatialElementBoundaryOptions())
    for loop in loops:
        for segment in loop:
            if DEBUG: print segment.GetCurve().GetEndPoint(0)
            if isinstance(doc.GetElement(segment.ElementId), Wall):
                wall = doc.GetElement(segment.ElementId)
                if DEBUG: print output.linkify(segment.ElementId) 
                wall_face_interior_refs = HostObjectUtils.GetSideFaces(wall, ShellLayerType.Interior)
                wall_face_exterior_refs = HostObjectUtils.GetSideFaces(wall, ShellLayerType.Exterior)
                for wfer in wall_face_exterior_refs:
                    wall_face_exterior = doc.GetElement(wfer).GetGeometryObjectFromReference(wfer)
                    if not wall_face_exterior == None:
                        res = wall_face_exterior.Intersect(segment.GetCurve())
                        if res != SetComparisonResult.Disjoint:
                            matr = doc.GetElement(wall_face_exterior.MaterialElementId)
                            newmat.add(matr.Name)
                            if DEBUG: print "exterior: " + matr.Name
                for wfir in wall_face_interior_refs:
                    wall_face_interior = doc.GetElement(wfir).GetGeometryObjectFromReference(wfir)
                    if not wall_face_interior == None:
                        res = wall_face_interior.Intersect(segment.GetCurve())
                        if res != SetComparisonResult.Disjoint:
                            matr = doc.GetElement(wall_face_interior.MaterialElementId)
                            newmat.add(matr.Name)
                            if DEBUG: print "interior: " + matr.Name
                        
    return join_mat(newmat)
    
def join_mat(materials):
    joined = ', '.join(materials)
    return joined

def owned_by_other_user(elem):
#from Autodesk.Revit.DB import CheckoutStatus, WorksharingUtils

    # Checkout Status of the element
    checkout_status = WorksharingUtils.GetCheckoutStatus(doc, elem.Id)
    if checkout_status == CheckoutStatus.OwnedByOtherUser:
        return True
    else:
        return False

def get_para_by_name(ref, parameter_name):
    myele = doc.GetElement(ref)
    wall_param_mat = myele.LookupParameter(parameter_name)
    
    if wall_param_mat.HasValue:
        wall_param_mat_str = wall_param_mat.AsString()
        return wall_param_mat_str
    else:
        return ""

def get_reference_by_direction(view, p, direction):
    filter = ElementClassFilter(DB.Floor)
    refIntersector = ReferenceIntersector(filter, FindReferenceTarget.Face, view)
    refIntersector.FindReferencesInRevitLinks = False
    if DEBUG: print p
    rwc = refIntersector.FindNearest(p, direction)
    if rwc is not None:
    
        r = rwc.GetReference()# if rwc else None
        if not r:
            print("no intersecting geometry")
        else:
            print output.linkify(r.ElementId)

        return r
    return
    
########################################################################   
# we have to run in a 3d view 
if not isinstance(doc.ActiveView, View3D):
    forms.alert('You must be on a 3D view for this tool to work.')
    script.exit()
    
UP = XYZ.BasisZ
DOWN = UP.Negate()    
stopwatch = Stopwatch()
stopwatch.Start()
idx = 0

output = script.get_output()

rooms = Fec(doc).OfCategory(Bic.OST_Rooms).WhereElementIsNotElementType().ToElements()

selection = [doc.GetElement(elId) for elId in uidoc.Selection.GetElementIds()]

#start transaction
with db.Transaction("write room data"):
    #if there was an slection we use them instead
    if selection:
        rooms = selection

    #for the process bar on top
    EleNums = rooms.Count         

    if EleNums ==0:
        forms.alert('There are no rooms to work with.')
        script.exit()
    
    #just on room to check if the parameters attached
    #TODO: check an other way to determine parameters
    room = rooms[0]
    if not param_exists_by_name(room, room_parameter_name_wall_materials):
        forms.alert("The parameter " + room_parameter_name_wall_materials + " is necessary but does not exist. Please create them first.")
        script.exit()
    if not param_exists_by_name(room, room_parameter_name_ceiling_materials):
        forms.alert("The parameter " + room_parameter_name_ceiling_materials + " is necessary but does not exist. Please create them first.")
        script.exit()
    if not param_exists_by_name(room, room_parameter_name_floor_materials):
        forms.alert("The parameter " + room_parameter_name_floor_materials + " is necessary but does not exist. Please create them first.")
        script.exit()
    if not param_exists_by_name(room, manual_room_materials_parameter_name):
        forms.alert("The parameter " + manual_room_materials_parameter_name + " is necessary but does not exist. Please create them first.")
        script.exit()

    #room by room
    for room in rooms:
        #check if someone else has the room, otherwise an error will thrown
        #TODO maybe this throw an error in a non worksharing model
        if owned_by_other_user(room):
            print(" Room number: " + room.Number + output.linkify(room.Id) + " -> OwnedByOtherUser") 
            continue
    
        #rooms where not placed as 0 area
        if not room.Area > 0:
            continue
        
        if DEBUG:
            room_name = room.get_Parameter(BuiltInParameter.ROOM_NAME).AsString()
            print(" Room number: " + room.Number + " " + output.linkify(room.Id) + " " + room_name)
        #else:
            #print(" Room number: " + room.Number + " " + output.linkify(room.Id))
    
        #there is a parameter that protects the room from being overwritten by this script
        manual = room.LookupParameter(manual_room_materials_parameter_name).AsInteger()

        if manual:
            print(" Room number: " + room.Number  + " " + output.linkify(room.Id) + " -> manual")
            continue

        else:

            wall_materials = retrieve_mat_from_room_boundaries(room)
            room_walls_param = room.LookupParameter(room_parameter_name_wall_materials)
            room_walls_param.Set(wall_materials)

            if DEBUG: print (room_parameter_name_wall_materials + " :" + wall_materials)

            center = (room.Location).Point

            r = None
            
            uppoint = XYZ(center.X , center.Y , center.Z + 4)
            #r = get_reference_by_direction(doc.ActiveView, center, UP)
            r = get_reference_by_direction(doc.ActiveView, uppoint, UP)
            
            if r is not None:
                ceiling_mat = get_para_by_name(r, wall_material_parameter_name)
                if ceiling_mat <> "None":
                    room_ceiling_param = room.LookupParameter(room_parameter_name_ceiling_materials)
                    room_ceiling_param.Set(str(ceiling_mat))
                    if DEBUG: print (room_parameter_name_ceiling_materials + ": " + str(ceiling_mat))

            r = get_reference_by_direction(doc.ActiveView, center, DOWN)

            if r is not None:
                floor_mat = get_para_by_name(r, wall_material_parameter_name)
                if floor_mat <> "None":
                    room_floor_param = room.LookupParameter(room_parameter_name_floor_materials)
                    room_floor_param.Set(str(floor_mat))
                    if DEBUG: print (room_parameter_name_floor_materials + ": " + str(floor_mat))

        output.update_progress(idx, EleNums)
        idx+=1   

output.reset_progress()

print(53 * "=")
stopwatch.Stop()
timespan = stopwatch.Elapsed
print("Run in: {}".format(timespan))
