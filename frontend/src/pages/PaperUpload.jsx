import {
  UploadCloud,
  FileText,
  CheckCircle,
  Clock
} from "lucide-react";


function PaperUpload(){

  const papers = [
    {
      name:"No papers uploaded yet",
      status:"Waiting"
    }
  ];


  return (

    <div className="text-white">


      {/* Header */}

      <div className="mb-8">

        <h1 className="
          text-3xl
          font-bold
        ">
          Upload Research Papers
        </h1>


        <p className="
          text-slate-400
          mt-2
        ">
          Upload academic papers to extract insights and build knowledge relationships.
        </p>

      </div>



      {/* Upload Box */}

      <div
        className="
          border-2
          border-dashed
          border-slate-700
          bg-slate-900
          rounded-xl
          p-10
          flex
          flex-col
          items-center
          justify-center
          hover:border-indigo-500
          transition
        "
      >

        <UploadCloud
          size={50}
          className="text-indigo-400"
        />


        <h2 className="
          text-xl
          font-semibold
          mt-4
        ">
          Upload PDF Research Paper
        </h2>


        <p className="
          text-slate-400
          mt-2
        ">
          Drag and drop your file here or browse from your computer
        </p>


        <button
          className="
            mt-6
            px-5
            py-2
            rounded-lg
            bg-indigo-600
            hover:bg-indigo-500
          "
        >
          Browse Files
        </button>


      </div>




      {/* Uploaded Papers */}

      <div
        className="
          mt-8
          bg-slate-900
          border
          border-slate-800
          rounded-xl
          p-6
        "
      >

        <h2 className="
          text-xl
          font-semibold
        ">
          Uploaded Papers
        </h2>


        <div className="
          mt-5
          space-y-3
        ">


        {
          papers.map((paper)=>(
            
            <div
              key={paper.name}
              className="
                flex
                justify-between
                items-center
                bg-slate-800
                p-4
                rounded-lg
              "
            >

              <div className="
                flex
                items-center
                gap-3
              ">

                <FileText
                  className="text-indigo-400"
                />

                <span>
                  {paper.name}
                </span>

              </div>



              <div className="
                flex
                items-center
                gap-2
                text-slate-400
              ">

                {
                  paper.status==="Completed"
                  ?
                  <CheckCircle size={18}/>
                  :
                  <Clock size={18}/>
                }

                {paper.status}

              </div>


            </div>

          ))

        }


        </div>


      </div>



    </div>

  )

}


export default PaperUpload;