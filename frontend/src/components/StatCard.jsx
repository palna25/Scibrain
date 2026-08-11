import { Card } from "./ui/card";


function StatCard({ title, value, icon: Icon }) {

  return (
    <Card
      className="
        bg-slate-900
        border-slate-800
        p-5
        text-white
      "
    >

      <div className="flex justify-between items-center">

        <div>

          <p className="text-sm text-slate-400">
            {title}
          </p>

          <h2 className="text-3xl font-bold mt-2">
            {value ?? "-"}
          </h2>

        </div>


        {Icon && (
          <Icon 
            size={32}
            className="text-indigo-400"
          />
        )}

      </div>

    </Card>
  );
}


export default StatCard;