import os
import struct

from typing import cast

from UM.Job import Job
from UM.Logger import Logger
from UM.Mesh.MeshReader import MeshReader
from UM.Mesh.MeshBuilder import MeshBuilder
from UM.MimeTypeDatabase import MimeTypeDatabase, MimeType
from UM.Scene.SceneNode import SceneNode

have_crc32c = False
try:
    import crc32c
    have_crc32c = True
except ImportError:
    Logger.log("w", "CRC32C not found, skipping SML integrity checks.")
    

class SMLReader(MeshReader):
    def __init__(self) -> None:
        super().__init__()
        MimeTypeDatabase.addMimeType(
            MimeType(
                name = "model/sml",
                comment = "SML File",
                suffixes = ["sml"]
            )
        )
        self._supported_extensions = [".sml"]

    def _read(self, file_name):
        scene_node = None

        extension = os.path.splitext(file_name)[1]
        if extension.lower() in self._supported_extensions:
            vertex_list = []
            scene_node = SceneNode()

            mesh_builder = MeshBuilder()
            mesh_builder.setFileName(file_name)
            f = open(file_name, "rb")

            f.seek(0, os.SEEK_END)
            size = f.tell()
            if size < 13:
                Logger.logException("e", "SML file truncated or empty: Size is less than 13 bytes.")
                return None
            f.seek(0, os.SEEK_SET)
            
            header = struct.unpack(b"4s", f.read(4))
            if header[0] != b"SML1" and header[0] != "SML1":
                Logger.logException("e", "SML header invalid. Expected 'SML1' got '%s'", header[0])
                return None
            
            crc = cast(int, struct.unpack("<I", f.read(4))[0])
            if have_crc32c:
                checkcrc = 0
                for i in range(8, size, 65536):
                    data = f.read(65536)
                    checkcrc = crc32c.crc32c(data, checkcrc)
                    Job.yieldThread()
                if crc != checkcrc:
                    Logger.log("e", "SML CRC check failed. Expected '{:#010x}' got '{:#010x}'".format(crc, checkcrc))
                    # May as well try to laod it anyhow, shouldn't do any harm.
                    #return None

            f.seek(8, os.SEEK_SET)
            pos = 8
            while pos < size:
                realpos = f.tell()
                if pos != realpos:
                    Logger.logException("e", "Summed position %s does not match actual position %s.", pos, realpos)
                    pos = realpos
                
                #Logger.log("i", "SML segment starting at position %s of size %s.", pos, size)
                segtype = cast(int, struct.unpack("B", f.read(1))[0])
                seglength = cast(int, struct.unpack("<I", f.read(4))[0])
                pos += 5
                if pos + seglength > size:
                    Logger.logException("e", "SML file truncated: Position %s + segment %s would exceed file size %s.", pos, seglength, size)
                    return None
                pos += seglength
                #Logger.log("i", "SML segment type %s, segment length %s.", segtype, seglength)
                    
                if segtype == 0: # Comment
                    f.seek(seglength, os.SEEK_CUR)
                    
                elif segtype == 1: # Float vertex list
                    count = seglength // 12
                    vertex_list = []
                    for i in range(count):
                        vertex = struct.unpack(b"<fff", f.read(12))
                        vertex_list.append([float(vertex[0]), float(vertex[2]), -float(vertex[1])])
                        #Logger.log("i", "Vertex: %s %s %s", float(vertex[0]), float(vertex[2]), -float(vertex[1]))
                        Job.yieldThread()
                    vertices = len(vertex_list)
                    Logger.log("i", "Loaded %s float vertices.", vertices)
                
                elif segtype == 2: # Double vertex list
                    count = seglength // 24
                    vertex_list = []
                    for i in range(count):
                        vertex = struct.unpack(b"<ddd", f.read(24))
                        vertex_list.append([float(vertex[0]), float(vertex[2]), -float(vertex[1])])
                        Job.yieldThread()
                    vertices = len(vertex_list)
                    Logger.log("i", "Loaded %s double vertices.", vertices)
                
                elif segtype == 3: # Triangle list
                    count = seglength // 12
                    for i in range(count):
                        face = struct.unpack(b"<III", f.read(12))
                        a = cast(int, face[0])
                        b = cast(int, face[1])
                        c = cast(int, face[2])
                        
                        #Logger.log("Triangle: %s %s %s", a, b, c)
                        if a >= vertices or b >= vertices or c >= vertices:
                            Logger.logException("e", "Vertex index out of range at %s: a=%s b=%s c=%s vertices=%s", i, a, b, c, vertices)
                            # We can just drop the triangle and keep going.
                            #return None
                            continue
                        
                        mesh_builder.addFaceByPoints(
                            vertex_list[a][0], vertex_list[a][1], vertex_list[a][2], 
                            vertex_list[b][0], vertex_list[b][1], vertex_list[b][2], 
                            vertex_list[c][0], vertex_list[c][1], vertex_list[c][2])

                        #Logger.log("Triangle: %s %s %s / %s %s %s / %s %s %s", 
                        #    vertex_list[a][0], vertex_list[a][1], vertex_list[a][2], 
                        #    vertex_list[b][0], vertex_list[b][1], vertex_list[b][2], 
                        #    vertex_list[c][0], vertex_list[c][1], vertex_list[c][2])
                        Job.yieldThread()
                
                elif segtype == 4: # Quad list
                    count = seglength // 16
                    for i in range(count):
                        face = struct.unpack(b"<IIII", f.read(16))
                        a = cast(int, face[0])
                        b = cast(int, face[1])
                        c = cast(int, face[2])
                        d = cast(int, face[3])

                        if a >= vertices or b >= vertices or c >= vertices or d >= vertices:
                            Logger.logException("e", "Vertex index out of range at %s: a=%s b=%s c=%s d=%s vertices=%s", i, a, b, c, d, vertices)
                            continue

                        mesh_builder.addFaceByPoints(
                            vertex_list[a][0], vertex_list[a][1], vertex_list[a][2], 
                            vertex_list[b][0], vertex_list[b][1], vertex_list[b][2], 
                            vertex_list[c][0], vertex_list[c][1], vertex_list[c][2])
                        mesh_builder.addFaceByPoints(
                            vertex_list[a][0], vertex_list[a][1], vertex_list[a][2], 
                            vertex_list[c][0], vertex_list[c][1], vertex_list[c][2], 
                            vertex_list[d][0], vertex_list[d][1], vertex_list[d][2])
                        Job.yieldThread()
                
                elif segtype == 5: # Triangle strip
                    count = seglength // 4

                    face = struct.unpack(b"<III", f.read(12))
                    a = int(face[0])
                    b = int(face[1])
                    c = int(face[2])
                    
                    if a >= vertices or b >= vertices or c >= vertices:
                        Logger.logException("e", "Vertex index out of range for strip initial triangle: a=%s b=%s c=%s vertices=%s", i, a, b, c, vertices)
                    else:
                        # With strips, the error will propagate for a bit, but assuming there's valid triangles down the road it should recover.
                        mesh_builder.addFaceByPoints(
                            vertex_list[a][0], vertex_list[a][1], vertex_list[a][2], 
                            vertex_list[b][0], vertex_list[b][1], vertex_list[b][2], 
                            vertex_list[c][0], vertex_list[c][1], vertex_list[c][2])
                        
                    for i in range(3, count):
                        if i & 1:
                            b = c
                        else:
                            a = c
                        c = cast(int, struct.unpack("<I", f.read(4))[0])

                        if c >= vertices:
                            Logger.logException("e", "Vertex index out of range at strip offset %s: c=%s vertices=%s", i, c, vertices)
                        else:
                            mesh_builder.addFaceByPoints(
                                vertex_list[a][0], vertex_list[a][1], vertex_list[a][2], 
                                vertex_list[b][0], vertex_list[b][1], vertex_list[b][2], 
                                vertex_list[c][0], vertex_list[c][1], vertex_list[c][2])
                        Job.yieldThread()
                 
                else: # Unsupported type, ignore it and hope for the best.
                    Logger.logException("e", "SML file contains unsupported segment type; ignoring.")
                    f.seek(seglength, os.SEEK_CUR)
                
                Job.yieldThread()
            f.close()
            
            mesh_builder.calculateNormals(fast = True)
            scene_node.setMeshData(mesh_builder.build())
        return scene_node
