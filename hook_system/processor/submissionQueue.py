from submission import Submission
from match import Match
from hookFile import HookFile
from hookFileType import HookFileType
from standardizedFile import StandardizedFile
from typing import List, Tuple
from datetime import datetime, timedelta
import tarfile as tar
import threading
import time
import os
import standardize
import winnow
import xmlGenerator

mutex = threading.Lock()
submissionQueue: List[Tuple[str, str]] = []


def addToQueue(filePath: str, emailAddr: str) -> Tuple[bool, str]:
    
    mutex.acquire()

    nPrior: int = len(submissionQueue)

    submissionQueue.append((filePath, emailAddr))

    nCur:int = len(submissionQueue)

    mutex.release()

    if nCur == nPrior+1:
        return True, datetime.now() + timedelta(minutes=5) #TODO find a formula for wait time
    else:
        return False, ""



def processQueue():
    
    while True:
        mutex.acquire()

        #Queue is empty wait to check again
        if not submissionQueue:
            mutex.release()
            time.sleep(5)
        else:
            filePath, emailAddr = submissionQueue.pop(0)
            mutex.release()

            cFiles: List[HookFile] = []
            cWhitelist: List[HookFile] = []

            javaFiles: List[HookFile] = []
            javaWhitelist: List[HookFile] = []

            with tar.open(filePath, mode='r') as tarFile:
                for fileName in tarFile.getnames():
                    if tarFile.getmember(fileName).isfile():

                        #Break up the file path into it's respective folders
                        filePathElements: List[str] = os.path.normpath(fileName).split(os.sep)
                        
                        ext = fileName[fileName.rfind('.'):] #Find the file extension

                        #This is a previous years submission so we need to use it to check for plagiarism but not actually
                        #check for plagiarism in this file
                        if filePathElements[0] == 'PreviousYears': 
                            owner = filePathElements[1].split('_')[-1] #Get the student hash in the folder name

                            if ext == ".java": #If it's a java file then add it to the java list
                                javaFiles.append(HookFile(fileName, owner, HookFileType.PREVIOUS_YEAR, tarFile.extractfile(fileName).read().decode('utf-8')))
                            elif ext == ".cpp" or ext == ".c" or ext == ".hpp" or ext == ".h": #If it's a C/C++ file add it to the C list
                                cFiles.append(HookFile(fileName, owner, HookFileType.PREVIOUS_YEAR, tarFile.extractfile(fileName).read().decode('utf-8')))

                        # This is a current year submission so we need to actually check for plagiarism in it
                        elif filePathElements[0] == 'CurrentYear':
                            owner = filePathElements[1].split('_')[-1] #Get the student hash in the folder name

                            if ext == ".java":
                                javaFiles.append(HookFile(fileName, owner, HookFileType.CURRENT_YEAR, tarFile.extractfile(fileName).read().decode('utf-8')))
                            elif ext == ".cpp" or ext == ".c" or ext == ".hpp" or ext == ".h":
                                cFiles.append(HookFile(fileName, owner, HookFileType.CURRENT_YEAR, tarFile.extractfile(fileName).read().decode('utf-8')))

                        #This is a whitelist piece of code which shouldn't return plagiarism if it exists in a students submission
                        elif filePathElements[0] == 'Exclusions':
                            if ext == ".java":
                                javaWhitelist.append(HookFile(fileName, "", None, tarFile.extractfile(fileName).read().decode('utf-8')))
                            elif ext == ".cpp" or ext == ".c" or ext == ".hpp" or ext == ".h":
                                cWhitelist.append(HookFile(fileName, "", None, tarFile.extractfile(fileName).read().decode('utf-8')))

            """
            The MOSS paper on Winnowing goes into detail on how the winnowing algorithm work's and why it is necessary to standardize the input.
            Section 3 of the paper explains the winnowing algorithm while Section 5.2 describes how to use the algorithm for plagiarism detection.
            The Paper can be found at https://theory.stanford.edu/~aiken/publications/papers/sigmod03.pdf
            """

            #Standardize the files to be processed, this includes removing variable names.
            cStandardized: List[StandardizedFile] = standardize.standardizeC(cFiles)
            cStandardizedWhitelist : List[StandardizedFile] = standardize.standardizeC(cWhitelist)

            javaStandardized: List[StandardizedFile] = standardize.standardizeJava(javaFiles)
            javaStandardizedWhitelist : List[StandardizedFile] = standardize.standardizeJava(javaWhitelist)

            #Apply the winnowing algorithm to the standardized files
            cMatches: List[Match] = winnow.getMatches(cStandardized, cStandardizedWhitelist)
            javaMatches: List[Match] = winnow.getMatches(javaStandardized, javaStandardizedWhitelist, len(cMatches))

            _, tarFilename = os.path.split(filePath)

            jobID: str = tarFilename.replace('.tar.gz','')

            allMatches: List[Match] = cMatches
            allMatches += javaMatches
            with open("./Results/"+jobID+".xml", 'wb') as f:
                f.write(xmlGenerator.generateResult(allMatches))

            os.remove(filePath)
                        
            #TODO SEND EMAIL 




def __sendEmail(emailAddr: str, msg: str) -> bool:
    return True